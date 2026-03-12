/**
 * unitRenderer — Unit/player rendering on the canvas.
 *
 * Extracted from ArenaRenderer.js (P4 refactoring).
 * Handles getUnitColor, drawPlayer (shape/sprite rendering),
 * drawBuffIcons (buff/debuff sprite icons below units),
 * drawStanceIndicators, drawUnderfootGlow, drawNameplateGlow,
 * drawSelectedTargetIndicator, drawTargetReticle,
 * and the _findSkillDef helper.
 *
 * Targeting Reticle Revamp: Replaced overlapping circle rings with a
 * layered system — underfoot radial glow + pulsing nameplate highlight.
 * Each unit shows at most ONE indicator type (priority: auto-target >
 * selected target > party selection). Skill highlights use corner ticks
 * instead of filled squares to reduce visual clutter.
 */

import {
  TILE_SIZE,
  ENEMY_COLORS, ENEMY_SHAPES, ENEMY_NAMES,
  CLASS_COLORS, CLASS_SHAPES, CLASS_NAMES,
  TEAM_COLORS,
} from './renderConstants.js';
import { isSpriteSheetLoaded, getSpriteKey, drawSprite } from './SpriteLoader.js';
import { getSkillIconImage, isSkillIconSheetLoaded } from '../components/BottomBar/SkillIconMap.js';

// ---------- Buff/Debuff Icon Sprites ----------
// Sprite regions from the 64x64 skill-icons.png sheet (same sheet as SkillIconMap).
// Keys are buff identifiers that map to active_buffs entries.
const BUFF_SPRITE_MAP = {
  // Buff types by stat name
  attack_buff:           { x: 0,   y: 2560, w: 64, h: 64 },
  attack_debuff:         { x: 64,  y: 2560, w: 64, h: 64 },
  armor_buff:            { x: 192, y: 2560, w: 64, h: 64 },
  armor_debuff:          { x: 256, y: 2560, w: 64, h: 64 },
  hp_buff:               { x: 128, y: 2432, w: 64, h: 64 },
  hp_debuff:             { x: 640, y: 2432, w: 64, h: 64 },
  magic_buff:            { x: 64,  y: 2432, w: 64, h: 64 },
  magic_debuff:          { x: 576, y: 2432, w: 64, h: 64 },
  magic_shield_buff:     { x: 192, y: 2432, w: 64, h: 64 },
  strength_debuff:       { x: 512, y: 2432, w: 64, h: 64 },
  movement_buff:         { x: 384, y: 2432, w: 64, h: 64 },
  movement_debuff:       { x: 896, y: 2432, w: 64, h: 64 },
};

/**
 * Resolve a buff entry from active_buffs to a sprite region key.
 * Maps buff_id, type, and stat fields to a BUFF_SPRITE_MAP key.
 */
function getBuffSpriteKey(buff) {
  // Try direct buff_id match first (e.g. "war_cry" -> mapped by type logic)
  const type = buff.type || 'buff';
  const stat = buff.stat || '';
  const isDebuff = type === 'dot' || type === 'debuff' || buff.magnitude < 0;

  // Map by stat name
  if (stat.includes('melee_damage') || stat.includes('attack'))
    return isDebuff ? 'attack_debuff' : 'attack_buff';
  if (stat.includes('armor'))
    return isDebuff ? 'armor_debuff' : 'armor_buff';
  if (stat.includes('hp') || stat.includes('max_hp'))
    return isDebuff ? 'hp_debuff' : 'hp_buff';
  if (stat.includes('magic') || stat.includes('ranged'))
    return isDebuff ? 'magic_debuff' : 'magic_buff';
  if (stat.includes('movement') || stat.includes('speed'))
    return isDebuff ? 'movement_debuff' : 'movement_buff';

  // Map by buff type
  if (type === 'dot') return 'hp_debuff';
  if (type === 'hot') return 'hp_buff';
  if (type === 'shield_charges') return 'magic_shield_buff';
  if (type === 'detection') return 'magic_buff';

  // Fallback
  return isDebuff ? 'attack_debuff' : 'attack_buff';
}

// ---------- Phase 18E: Monster Rarity Visual Constants ----------

/** Name text colors per rarity tier (E2) */
const RARITY_NAME_COLORS = {
  normal:       '#ffffff',
  champion:     '#6688ff',
  rare:         '#ffcc00',
  super_unique: '#cc66ff',
};

/** Outline glow colors per rarity tier (E3) */
const RARITY_GLOW_COLORS = {
  champion:     { r: 102, g: 136, b: 255 },  // blue
  rare:         { r: 255, g: 204, b: 0 },    // gold
  super_unique: { r: 204, g: 102, b: 255 },  // purple
};

/** Outline glow thickness per rarity tier (E3) */
const RARITY_GLOW_WIDTH = {
  champion:     2,
  rare:         3,
  super_unique: 3,
};

/** Phase 18E (E4): Champion type tint colors (from visual_tint in config) */
const CHAMPION_TINT_COLORS = {
  berserker: { r: 255, g: 68,  b: 68,  baseAlpha: 0.18 },
  fanatic:   { r: 255, g: 204, b: 68,  baseAlpha: 0.15 },
  ghostly:   null, // handled by globalAlpha in E6
  resilient: { r: 136, g: 136, b: 153, baseAlpha: 0.20 },
  possessed: { r: 153, g: 68,  b: 204, baseAlpha: 0.22 },
};

/** Size scale per rarity tier (E2) */
const RARITY_SIZE_SCALE = {
  normal:       1.0,
  champion:     1.0,
  rare:         1.1,
  super_unique: 1.2,
};

// ---------- Drop Shadow & Elevation Constants ----------
// Elevation offset lifts sprites upward to create depth; shadow stays at ground level.
const ELEVATION_OFFSET = 4; // pixels the sprite is lifted above tile center
const SHADOW_OPACITY = 0.38; // base opacity of the drop shadow ellipse

// ---------- Combined Diablo-Style Plate Constants ----------
const PLATE_HEIGHT = 26;
const PLATE_BAR_HEIGHT = 6;

// ---------- Compact Plate Constants (Nameplate Declutter System) ----------
// Compact mode: HP-bar-only, fits within one tile width to eliminate overlap
const COMPACT_PLATE_WIDTH = 44;       // narrower than TILE_SIZE (48) — no horizontal overflow
const COMPACT_PLATE_WIDTH_BOSS = 56;  // bosses still slightly wider
const COMPACT_PLATE_HEIGHT = 10;      // just the bar + tiny border
const COMPACT_BAR_HEIGHT = 5;         // slightly smaller bar

// ---------- Phase B3: Smooth Expand/Collapse Animation ----------
// Time-based lerp between compact and full plate dimensions over ~150ms.
// Uses real clock time so animation speed is consistent regardless of framerate.
const _plateExpandCache = new Map();
const PLATE_EXPAND_DURATION = 150; // ms for full expand or collapse

function _getExpandProgress(unitId, targetMode) {
  const target = targetMode === 'full' ? 1 : 0;
  const now = performance.now();
  if (!_plateExpandCache.has(unitId)) {
    _plateExpandCache.set(unitId, { progress: target, lastTime: now });
    return target;
  }
  const entry = _plateExpandCache.get(unitId);
  const dt = now - entry.lastTime;
  entry.lastTime = now;
  // Move toward target at a constant rate (full 0→1 in PLATE_EXPAND_DURATION ms)
  const step = dt / PLATE_EXPAND_DURATION;
  if (entry.progress < target) {
    entry.progress = Math.min(target, entry.progress + step);
  } else if (entry.progress > target) {
    entry.progress = Math.max(target, entry.progress - step);
  }
  return entry.progress;
}

/**
 * Get the pixel-space rect for the combined nameplate above a unit.
 * Shared by drawPlayer, drawBuffIcons, and drawNameplateGlow for consistent positioning.
 * Fixed widths keep all nameplates uniform regardless of name length.
 */
function _getPlateRect(cx, ey, isBoss) {
  const radius = isBoss ? TILE_SIZE * 0.42 : TILE_SIZE * 0.35;
  const plateWidth = isBoss ? 84 : 72;
  const plateX = cx - plateWidth / 2;
  const plateY = ey - radius - PLATE_HEIGHT - 3;
  return { plateX, plateY, plateWidth, plateHeight: PLATE_HEIGHT };
}

/**
 * Get the pixel-space rect for a compact HP-bar-only plate above a unit.
 * Used when nameplateMode === 'compact' to reduce clutter in crowded areas.
 */
function _getCompactPlateRect(cx, ey, isBoss) {
  const radius = isBoss ? TILE_SIZE * 0.42 : TILE_SIZE * 0.35;
  const plateWidth = isBoss ? COMPACT_PLATE_WIDTH_BOSS : COMPACT_PLATE_WIDTH;
  const plateX = cx - plateWidth / 2;
  const plateY = ey - radius - COMPACT_PLATE_HEIGHT - 2;
  return { plateX, plateY, plateWidth, plateHeight: COMPACT_PLATE_HEIGHT };
}

// ---------- HP Animation Cache ----------
// Smooth HP bar lerp + flash on damage/heal per unit ID
const _hpAnimCache = new Map();

function _getAnimatedHp(unitId, currentHp, maxHp) {
  if (!unitId) return { displayHp: currentHp, flashColor: null, flashAlpha: 0 };

  if (!_hpAnimCache.has(unitId)) {
    _hpAnimCache.set(unitId, { displayHp: currentHp, targetHp: currentHp, lastChangeTime: 0, flashColor: null });
    return { displayHp: currentHp, flashColor: null, flashAlpha: 0 };
  }

  const entry = _hpAnimCache.get(unitId);
  const now = Date.now();

  if (currentHp !== entry.targetHp) {
    entry.flashColor = currentHp < entry.targetHp ? 'rgba(255,60,60,0.6)' : 'rgba(100,255,100,0.5)';
    entry.lastChangeTime = now;
    entry.targetHp = currentHp;
  }

  // Lerp toward target over successive frames
  entry.displayHp += (entry.targetHp - entry.displayHp) * 0.15;
  if (Math.abs(entry.displayHp - entry.targetHp) < 0.5) {
    entry.displayHp = entry.targetHp;
  }

  // Flash fades over 300ms
  const flashAge = now - entry.lastChangeTime;
  const flashAlpha = flashAge < 300 ? 1 - (flashAge / 300) : 0;

  return { displayHp: entry.displayHp, flashColor: flashAlpha > 0 ? entry.flashColor : null, flashAlpha };
}

/**
 * Draw a dark elliptical drop shadow at the unit's feet.
 * Called BEFORE the sprite so the shadow sits underneath.
 * The shadow stays at ground level while the sprite is drawn elevated.
 *
 * @param {CanvasRenderingContext2D} ctx
 * @param {number} x - Tile X (viewport-adjusted)
 * @param {number} y - Tile Y (viewport-adjusted)
 * @param {boolean} [isBoss=false] - Boss units get a larger shadow
 */
export function drawUnitShadow(ctx, x, y, isBoss = false) {
  const cx = x * TILE_SIZE + TILE_SIZE / 2;
  // Shadow sits at the bottom portion of the tile (ground level)
  const shadowY = y * TILE_SIZE + TILE_SIZE * 0.72;
  const radiusX = isBoss ? TILE_SIZE * 0.34 : TILE_SIZE * 0.28;
  const radiusY = radiusX * 0.45; // flattened for ground-plane perspective

  ctx.save();
  const gradient = ctx.createRadialGradient(cx, shadowY, 0, cx, shadowY, radiusX);
  gradient.addColorStop(0, `rgba(0, 0, 0, ${SHADOW_OPACITY})`);
  gradient.addColorStop(0.6, `rgba(0, 0, 0, ${SHADOW_OPACITY * 0.5})`);
  gradient.addColorStop(1, 'rgba(0, 0, 0, 0)');
  ctx.fillStyle = gradient;
  ctx.beginPath();
  ctx.ellipse(cx, shadowY, radiusX, radiusY, 0, 0, Math.PI * 2);
  ctx.fill();
  ctx.restore();
}

/**
 * Get appropriate color for a unit based on enemy type, class, or team relationship.
 * Phase 4C: Enemy type color takes highest priority for dungeon enemies.
 * Phase 4A: If the unit has a class_id, use the class color.
 * Otherwise falls back to team-based coloring.
 */
export function getUnitColor(unitId, unitData, myPlayerId, myTeam, index) {
  // Enemy type coloring takes highest priority (dungeon enemies)
  if (unitData.enemy_type && ENEMY_COLORS[unitData.enemy_type]) {
    return ENEMY_COLORS[unitData.enemy_type];
  }

  // Class-based coloring takes priority
  if (unitData.class_id && CLASS_COLORS[unitData.class_id]) {
    return CLASS_COLORS[unitData.class_id];
  }

  if (unitId === myPlayerId) return '#4a9ff5'; // Always blue for self

  const isSameTeam = unitData.team === myTeam;
  if (isSameTeam) return TEAM_COLORS.ally;
  return TEAM_COLORS.enemy;
}

export function drawPlayer(ctx, x, y, color = '#4af', label = '', hp = 100, maxHp = 100, isAlive = true, unitType = 'human', classId = null, enemyType = null, isBoss = false, spriteVariant = 1, unitId = null, monsterRarity = null, championType = null, nameplateMode = 'full') {
  const cx = x * TILE_SIZE + TILE_SIZE / 2;
  const cy = y * TILE_SIZE + TILE_SIZE / 2;
  // Elevated center — sprite/shape draws lifted upward for depth illusion
  const ey = cy - (isAlive ? ELEVATION_OFFSET : 0);
  // Phase 18E: Apply size modifier per rarity tier
  const sizeScale = (monsterRarity && RARITY_SIZE_SCALE[monsterRarity]) || 1.0;
  // Boss enemies get a slightly larger radius, rarity may scale further
  const baseRadius = isBoss ? TILE_SIZE * 0.42 : TILE_SIZE * 0.35;
  const radius = baseRadius * sizeScale;

  if (!isAlive) {
    // Dead player — faded X marker (no elevation for corpses)
    ctx.strokeStyle = '#555';
    ctx.lineWidth = 2;
    ctx.beginPath();
    ctx.moveTo(cx - 8, cy - 8);
    ctx.lineTo(cx + 8, cy + 8);
    ctx.moveTo(cx + 8, cy - 8);
    ctx.lineTo(cx - 8, cy + 8);
    ctx.stroke();
    return;
  }

  // Phase 18E (E6): Ghostly champion type — render at 50% alpha
  const isGhostly = championType === 'ghostly';
  if (isGhostly) {
    ctx.save();
    ctx.globalAlpha = 0.5;
  }

  // Phase 18E (E3): Rarity outline glow — pulsing colored border per tier
  const rarityGlow = monsterRarity && RARITY_GLOW_COLORS[monsterRarity];
  if (rarityGlow) {
    const now = Date.now();
    const pulse = 0.5 + 0.5 * Math.sin(now / 600);
    const glowWidth = RARITY_GLOW_WIDTH[monsterRarity] || 2;
    const { r, g, b } = rarityGlow;
    // Outer diffuse glow
    ctx.save();
    ctx.strokeStyle = `rgba(${r}, ${g}, ${b}, ${0.15 + pulse * 0.2})`;
    ctx.lineWidth = glowWidth + 3;
    ctx.beginPath();
    ctx.arc(cx, ey, radius + glowWidth + 2, 0, Math.PI * 2);
    ctx.stroke();
    // Inner crisp border
    ctx.strokeStyle = `rgba(${r}, ${g}, ${b}, ${0.5 + pulse * 0.4})`;
    ctx.lineWidth = glowWidth;
    ctx.beginPath();
    ctx.arc(cx, ey, radius + glowWidth, 0, Math.PI * 2);
    ctx.stroke();
    ctx.restore();
  }



  // --- Try sprite rendering first (drawn at elevated position) ---
  const spriteKey = getSpriteKey(classId, enemyType, spriteVariant);
  let usedSprite = false;

  if (spriteKey && isSpriteSheetLoaded()) {
    // Sprite size: fill most of the tile, slightly padded; scaled by rarity
    const baseSpriteSize = isBoss ? TILE_SIZE * 0.9 : TILE_SIZE * 0.8;
    const spriteSize = baseSpriteSize * sizeScale;
    const destX = cx - spriteSize / 2;
    const destY = ey - spriteSize / 2;
    usedSprite = drawSprite(ctx, spriteKey, destX, destY, spriteSize, spriteSize);
  }

  // --- Fallback to shape rendering if no sprite available ---
  if (!usedSprite) {
    // Determine shape: enemy type → class shape → unit_type fallback
    let shape;
    if (enemyType && ENEMY_SHAPES[enemyType]) {
      shape = ENEMY_SHAPES[enemyType];
    } else if (classId && CLASS_SHAPES[classId]) {
      shape = CLASS_SHAPES[classId];
    } else {
      shape = unitType === 'ai' ? 'diamond' : 'circle';
    }

    ctx.fillStyle = color;
    ctx.strokeStyle = '#fff';
    ctx.lineWidth = 1.5;

    switch (shape) {
      case 'square':
        ctx.fillRect(cx - radius, ey - radius, radius * 2, radius * 2);
        ctx.strokeRect(cx - radius, ey - radius, radius * 2, radius * 2);
        break;
      case 'triangle':
        ctx.beginPath();
        ctx.moveTo(cx, ey - radius);
        ctx.lineTo(cx + radius, ey + radius * 0.7);
        ctx.lineTo(cx - radius, ey + radius * 0.7);
        ctx.closePath();
        ctx.fill();
        ctx.stroke();
        break;
      case 'diamond':
        ctx.beginPath();
        ctx.moveTo(cx, ey - radius);
        ctx.lineTo(cx + radius, ey);
        ctx.lineTo(cx, ey + radius);
        ctx.lineTo(cx - radius, ey);
        ctx.closePath();
        ctx.fill();
        ctx.stroke();
        break;
      case 'star': {
        const spikes = 5;
        const outerR = radius;
        const innerR = radius * 0.5;
        ctx.beginPath();
        for (let i = 0; i < spikes * 2; i++) {
          const r = i % 2 === 0 ? outerR : innerR;
          const angle = (Math.PI / 2 * 3) + (i * Math.PI / spikes);
          const sx = cx + Math.cos(angle) * r;
          const sy = ey + Math.sin(angle) * r;
          if (i === 0) ctx.moveTo(sx, sy);
          else ctx.lineTo(sx, sy);
        }
        ctx.closePath();
        ctx.fill();
        ctx.stroke();
        break;
      }
      case 'hexagon': {
        const sides = 6;
        ctx.beginPath();
        for (let i = 0; i < sides; i++) {
          const angle = (Math.PI / 3) * i - Math.PI / 6;
          const hx = cx + Math.cos(angle) * radius;
          const hy = ey + Math.sin(angle) * radius;
          if (i === 0) ctx.moveTo(hx, hy);
          else ctx.lineTo(hx, hy);
        }
        ctx.closePath();
        ctx.fill();
        ctx.stroke();
        break;
      }
      case 'crescent': {
        // Crescent moon / sound wave shape for Bard
        ctx.beginPath();
        ctx.arc(cx, ey, radius, 0.3 * Math.PI, 1.7 * Math.PI, false);
        ctx.arc(cx + radius * 0.35, ey, radius * 0.7, 1.7 * Math.PI, 0.3 * Math.PI, true);
        ctx.closePath();
        ctx.fill();
        ctx.stroke();
        break;
      }
      case 'shield': {
        // Kite shield / heraldic shield shape for Blood Knight
        const shW = radius * 0.85;
        const shH = radius * 1.1;
        ctx.beginPath();
        ctx.moveTo(cx, ey - shH);                          // top center
        ctx.quadraticCurveTo(cx + shW, ey - shH * 0.6,     // top-right curve
                             cx + shW, ey - shH * 0.1);    // right shoulder
        ctx.lineTo(cx + shW * 0.5, ey + shH * 0.5);        // right lower
        ctx.lineTo(cx, ey + shH);                           // bottom point
        ctx.lineTo(cx - shW * 0.5, ey + shH * 0.5);        // left lower
        ctx.lineTo(cx - shW, ey - shH * 0.1);              // left shoulder
        ctx.quadraticCurveTo(cx - shW, ey - shH * 0.6,     // top-left curve
                             cx, ey - shH);                 // back to top
        ctx.closePath();
        ctx.fill();
        ctx.stroke();
        break;
      }
      case 'flask': {
        // Alchemical flask — round bottom tapering to a narrow neck with a small opening (Plague Doctor)
        const r = radius * 0.75;
        ctx.beginPath();
        // Neck (narrow top)
        ctx.moveTo(cx - r * 0.2, ey - r);
        ctx.lineTo(cx + r * 0.2, ey - r);
        ctx.lineTo(cx + r * 0.2, ey - r * 0.5);
        // Shoulders
        ctx.lineTo(cx + r * 0.7, ey - r * 0.2);
        // Round body
        ctx.quadraticCurveTo(cx + r, ey + r * 0.3, cx + r * 0.5, ey + r * 0.8);
        ctx.lineTo(cx - r * 0.5, ey + r * 0.8);
        ctx.quadraticCurveTo(cx - r, ey + r * 0.3, cx - r * 0.7, ey - r * 0.2);
        // Back to neck
        ctx.lineTo(cx - r * 0.2, ey - r * 0.5);
        ctx.closePath();
        ctx.fill();
        ctx.stroke();
        break;
      }
      case 'coffin': {
        // Coffin/sarcophagus shape for Revenant — wider at shoulders, tapers at head and foot
        const cofW = half * 0.65;
        const cofH = half * 0.95;
        ctx.beginPath();
        ctx.moveTo(cx - cofW * 0.6, ey - cofH);          // top left (narrow head)
        ctx.lineTo(cx + cofW * 0.6, ey - cofH);          // top right (narrow head)
        ctx.lineTo(cx + cofW, ey - cofH * 0.4);           // shoulder right (wider)
        ctx.lineTo(cx + cofW * 0.5, ey + cofH);           // bottom right (narrow foot)
        ctx.lineTo(cx - cofW * 0.5, ey + cofH);           // bottom left (narrow foot)
        ctx.lineTo(cx - cofW, ey - cofH * 0.4);           // shoulder left (wider)
        ctx.closePath();
        ctx.fill();
        ctx.stroke();
        break;
      }
      case 'totem': {
        // Totem pole — stacked segments with carved faces, wider base (Shaman)
        const tw = half * 0.4;
        const th = half * 0.9;
        ctx.beginPath();
        // Top segment (head — narrow)
        ctx.moveTo(cx - tw * 0.8, ey - th);
        ctx.lineTo(cx + tw * 0.8, ey - th);
        ctx.lineTo(cx + tw, ey - th * 0.3);
        // Middle segment (body)
        ctx.lineTo(cx + tw * 1.2, ey - th * 0.3);
        ctx.lineTo(cx + tw * 1.2, ey + th * 0.3);
        // Bottom segment (base — wider)
        ctx.lineTo(cx + tw * 1.4, ey + th * 0.3);
        ctx.lineTo(cx + tw * 1.4, ey + th);
        ctx.lineTo(cx - tw * 1.4, ey + th);
        ctx.lineTo(cx - tw * 1.4, ey + th * 0.3);
        ctx.lineTo(cx - tw * 1.2, ey + th * 0.3);
        ctx.lineTo(cx - tw * 1.2, ey - th * 0.3);
        ctx.lineTo(cx - tw, ey - th * 0.3);
        ctx.closePath();
        ctx.fill();
        ctx.stroke();
        // Segment lines (carved face divisions)
        ctx.strokeStyle = 'rgba(0,0,0,0.3)';
        ctx.lineWidth = 1;
        ctx.beginPath();
        ctx.moveTo(cx - tw * 1.2, ey - th * 0.3);
        ctx.lineTo(cx + tw * 1.2, ey - th * 0.3);
        ctx.moveTo(cx - tw * 1.4, ey + th * 0.3);
        ctx.lineTo(cx + tw * 1.4, ey + th * 0.3);
        ctx.stroke();
        break;
      }
      case 'circle':
      default:
        ctx.beginPath();
        ctx.arc(cx, ey, radius, 0, Math.PI * 2);
        ctx.fill();
        ctx.stroke();
        break;
    }
  }

  // Phase 18E (E4): Champion type tint overlay — colored translucent layer over sprite/shape
  if (championType && CHAMPION_TINT_COLORS[championType]) {
    const tint = CHAMPION_TINT_COLORS[championType];
    const now = Date.now();
    let tintAlpha = tint.baseAlpha;

    if (championType === 'berserker') {
      // Berserker: pulsing red tint; pulses faster when below 30% HP (enraged)
      const hpRatio = maxHp > 0 ? hp / maxHp : 1;
      const isEnraged = hpRatio <= 0.30;
      const pulseSpeed = isEnraged ? 200 : 800;
      const pulse = 0.5 + 0.5 * Math.sin(now / pulseSpeed);
      tintAlpha = isEnraged ? (0.15 + pulse * 0.25) : (tint.baseAlpha + pulse * 0.08);
    } else if (championType === 'possessed') {
      // Possessed: dark purple shadow wisps — slight flicker
      const flicker = 0.7 + 0.3 * Math.sin(now / 400) * Math.cos(now / 170);
      tintAlpha = tint.baseAlpha * flicker;
    }

    ctx.save();
    ctx.globalCompositeOperation = 'source-atop';
    ctx.fillStyle = `rgba(${tint.r}, ${tint.g}, ${tint.b}, ${tintAlpha})`;
    ctx.beginPath();
    ctx.arc(cx, ey, radius + 1, 0, Math.PI * 2);
    ctx.fill();
    ctx.restore();

    // Resilient: extra thick outline (stone skin visual)
    if (championType === 'resilient') {
      ctx.save();
      ctx.strokeStyle = `rgba(${tint.r}, ${tint.g}, ${tint.b}, 0.45)`;
      ctx.lineWidth = 4;
      ctx.beginPath();
      ctx.arc(cx, ey, radius + 1, 0, Math.PI * 2);
      ctx.stroke();
      ctx.restore();
    }
  }

  // --- Diablo-style Combined Nameplate + HP Bar ---
  // Use the label passed in (already resolved by ArenaRenderer: display_name > ENEMY_NAMES > username).
  // Only fall back to ENEMY_NAMES if label is empty/missing.
  const displayLabel = label || ((enemyType && ENEMY_NAMES[enemyType]) ? ENEMY_NAMES[enemyType] : '');

  // --- Nameplate Declutter: Smooth interpolated drawing (Phase B3) ---
  // expandProgress lerps 0 (compact) → 1 (full) for smooth expand/collapse transitions.
  const expandProgress = _getExpandProgress(unitId, nameplateMode);
  const p0 = expandProgress; // shorthand: 0 = compact, 1 = full

  // Interpolate plate dimensions between compact and full
  const fullPlate = _getPlateRect(cx, ey, isBoss);
  const compactPlate = _getCompactPlateRect(cx, ey, isBoss);
  const plateWidth = compactPlate.plateWidth + (fullPlate.plateWidth - compactPlate.plateWidth) * p0;
  const plateHeight = compactPlate.plateHeight + (fullPlate.plateHeight - compactPlate.plateHeight) * p0;
  const plateX = cx - plateWidth / 2;
  const plateY = compactPlate.plateY + (fullPlate.plateY - compactPlate.plateY) * p0;
  const barHeight = COMPACT_BAR_HEIGHT + (PLATE_BAR_HEIGHT - COMPACT_BAR_HEIGHT) * p0;
  const borderRadius = 2 + p0; // 2 compact → 3 full

  ctx.save();

  // Dark semi-transparent plate background (opacity interpolates 0.65 → 0.72)
  const bgAlpha = 0.65 + 0.07 * p0;
  ctx.fillStyle = `rgba(8, 6, 12, ${bgAlpha.toFixed(3)})`;
  ctx.beginPath();
  ctx.roundRect(plateX, plateY, plateWidth, plateHeight, borderRadius);
  ctx.fill();

  // Thin dark border (thickness interpolates 0.75 → 1.0)
  ctx.strokeStyle = `rgba(60, 55, 70, ${(0.7 + 0.1 * p0).toFixed(3)})`;
  ctx.lineWidth = 0.75 + 0.25 * p0;
  ctx.stroke();

  // Phase 18E (E2): Determine name color — rarity color takes priority over class/enemy color
  const nameColor = (monsterRarity && RARITY_NAME_COLORS[monsterRarity]) || color;
  const accentColor = (monsterRarity && monsterRarity !== 'normal' && RARITY_NAME_COLORS[monsterRarity]) || color;

  // Class/enemy (or rarity) color accent stripe — fades in during expand
  if (p0 > 0.1) {
    ctx.save();
    ctx.globalAlpha = p0 * 0.45;
    ctx.fillStyle = accentColor;
    ctx.fillRect(plateX + 3, plateY + 1, plateWidth - 6, 1);
    ctx.restore();
  }

  // Name text — fades in during the latter portion of the expand transition
  // Phase 18E (E2): Rarity-colored names with black stroke outline.
  const nameAlpha = Math.max(0, (p0 - 0.3) / 0.7); // 0 at p0≤0.3, 1 at p0=1.0
  if (displayLabel && nameAlpha > 0.01) {
    const nameAreaCenterY = plateY + (plateHeight - barHeight) / 2;
    const fontSize = 10;
    const fontWeight = monsterRarity === 'super_unique' ? '900' : 'bold';
    const maxTextWidth = plateWidth - 8;

    ctx.font = `${fontWeight} ${fontSize}px Cinzel, Georgia, serif`;

    // Truncate with ellipsis if name exceeds plate width
    let renderLabel = displayLabel;
    if (ctx.measureText(renderLabel).width > maxTextWidth) {
      while (renderLabel.length > 1 && ctx.measureText(renderLabel + '\u2026').width > maxTextWidth) {
        renderLabel = renderLabel.slice(0, -1);
      }
      renderLabel += '\u2026';
    }

    ctx.save();
    ctx.globalAlpha = nameAlpha;
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';
    ctx.strokeStyle = '#000';
    ctx.lineWidth = 2;
    ctx.lineJoin = 'round';
    ctx.strokeText(renderLabel, cx, nameAreaCenterY);
    ctx.fillStyle = nameColor;
    ctx.fillText(renderLabel, cx, nameAreaCenterY);
    ctx.restore();
  }

  // HP bar — positioned at bottom of the interpolated plate
  if (maxHp > 0) {
    const barInset = 2 + p0; // 2 compact → 3 full
    const barX = plateX + barInset;
    const barY = plateY + plateHeight - barHeight - (1 + p0); // tighter compact, looser full
    const barW = plateWidth - barInset * 2;

    // Smooth HP animation
    const { displayHp, flashColor, flashAlpha } = _getAnimatedHp(unitId, hp, maxHp);
    const hpRatio = Math.max(0, Math.min(1, displayHp / maxHp));
    const actualRatio = Math.max(0, hp / maxHp);

    // Bar background (dark inset)
    ctx.fillStyle = 'rgba(15, 12, 20, 0.9)';
    ctx.beginPath();
    ctx.roundRect(barX, barY, barW, barHeight, 2);
    ctx.fill();

    // HP fill with gradient for depth
    if (hpRatio > 0) {
      const fillW = Math.max(3 + p0, barW * hpRatio);
      const hpGrad = ctx.createLinearGradient(barX, barY, barX, barY + barHeight);
      if (actualRatio > 0.5) {
        hpGrad.addColorStop(0, '#5fcc5f');
        hpGrad.addColorStop(1, '#2e8a2e');
      } else if (actualRatio > 0.25) {
        hpGrad.addColorStop(0, '#e8cc44');
        hpGrad.addColorStop(1, '#b8962e');
      } else {
        hpGrad.addColorStop(0, '#dd4444');
        hpGrad.addColorStop(1, '#992222');
      }
      ctx.fillStyle = hpGrad;
      ctx.beginPath();
      ctx.roundRect(barX, barY, fillW, barHeight, 2);
      ctx.fill();
    }

    // Flash overlay on HP change (damage = red flash, heal = green flash)
    if (flashColor && flashAlpha > 0) {
      ctx.save();
      ctx.globalAlpha = flashAlpha * 0.5;
      ctx.fillStyle = flashColor;
      ctx.beginPath();
      ctx.roundRect(barX, barY, barW, barHeight, 2);
      ctx.fill();
      ctx.restore();
    }

    // Notch marks — compact: 50% only; full: 25% / 50% / 75%
    ctx.strokeStyle = p0 >= 0.5 ? 'rgba(0, 0, 0, 0.35)' : 'rgba(0, 0, 0, 0.3)';
    ctx.lineWidth = 0.75 + 0.25 * p0;
    const notches = p0 >= 0.5 ? [0.25, 0.5, 0.75] : [0.5];
    for (const pct of notches) {
      const nx = barX + barW * pct;
      ctx.beginPath();
      ctx.moveTo(nx, barY + 1);
      ctx.lineTo(nx, barY + barHeight - 1);
      ctx.stroke();
    }

    // Subtle inner bar border — fades in during full expansion
    if (p0 > 0.5) {
      ctx.save();
      ctx.globalAlpha = (p0 - 0.5) * 2; // 0 at p0=0.5, 1 at p0=1.0
      ctx.strokeStyle = 'rgba(80, 75, 90, 0.5)';
      ctx.lineWidth = 0.5;
      ctx.beginPath();
      ctx.roundRect(barX, barY, barW, barHeight, 2);
      ctx.stroke();
      ctx.restore();
    }
  }

  // Phase 18E (E3): Rarity-colored plate border (interpolated thickness)
  if (rarityGlow) {
    const { r, g, b } = rarityGlow;
    ctx.strokeStyle = `rgba(${r}, ${g}, ${b}, ${(0.5 + 0.1 * p0).toFixed(3)})`;
    ctx.lineWidth = 1 + 0.5 * p0; // 1.0 compact → 1.5 full
    ctx.beginPath();
    ctx.roundRect(plateX - 0.5, plateY - 0.5, plateWidth + 1, plateHeight + 1, borderRadius + 1);
    ctx.stroke();
    // Outer glow — fades in during expand
    if (p0 > 0.3) {
      ctx.save();
      ctx.globalAlpha = (p0 - 0.3) / 0.7;
      ctx.strokeStyle = `rgba(${r}, ${g}, ${b}, 0.15)`;
      ctx.lineWidth = 3;
      ctx.stroke();
      ctx.restore();
    }
  } else if (isBoss && p0 > 0.3) {
    // Fallback: Boss plate golden ornamental border — fades in during expand
    ctx.save();
    ctx.globalAlpha = (p0 - 0.3) / 0.7;
    ctx.strokeStyle = 'rgba(255, 180, 50, 0.6)';
    ctx.lineWidth = 1.5;
    ctx.beginPath();
    ctx.roundRect(plateX - 0.5, plateY - 0.5, plateWidth + 1, plateHeight + 1, borderRadius + 1);
    ctx.stroke();
    ctx.strokeStyle = 'rgba(255, 200, 80, 0.15)';
    ctx.lineWidth = 3;
    ctx.stroke();
    ctx.restore();
  }

  ctx.restore();

  // Phase 18E (E6): Restore alpha after ghostly rendering
  if (isGhostly) {
    ctx.restore();
  }
}

/**
 * Draw buff/debuff sprite icons centered above the combined nameplate.
 * Shows small icons from the 64x64 skill-icons.png sheet in a centered
 * horizontal row above the plate. Each icon has a dark badge with turn count.
 * Debuffs get a red tint + red border. Max 4 icons shown.
 */
const BUFF_ICON_SIZE = 12;
const BUFF_ICON_GAP = 2;
const MAX_BUFF_ICONS = 4;

export function drawBuffIcons(ctx, x, y, activeBuffs, isBoss = false, displayLabel = '', color = '#fff', nameplateMode = 'full') {
  if (!activeBuffs || activeBuffs.length === 0) return;

  const iconImg = getSkillIconImage();
  const sheetReady = isSkillIconSheetLoaded() && iconImg;

  const cx = x * TILE_SIZE + TILE_SIZE / 2;
  const ey = y * TILE_SIZE + TILE_SIZE / 2 - ELEVATION_OFFSET;

  // Position centered above the plate (use compact rect when in compact mode)
  const plate = nameplateMode === 'compact'
    ? _getCompactPlateRect(cx, ey, isBoss)
    : _getPlateRect(cx, ey, isBoss);
  const buffsToShow = activeBuffs.slice(0, MAX_BUFF_ICONS);
  const hasOverflow = activeBuffs.length > MAX_BUFF_ICONS;
  const totalIconWidth = buffsToShow.length * (BUFF_ICON_SIZE + BUFF_ICON_GAP) - BUFF_ICON_GAP
    + (hasOverflow ? 16 : 0);
  const startX = cx - totalIconWidth / 2;
  const iconBaseY = plate.plateY - BUFF_ICON_SIZE - 3;

  for (let i = 0; i < buffsToShow.length; i++) {
    const buff = buffsToShow[i];
    const spriteKey = getBuffSpriteKey(buff);
    const region = BUFF_SPRITE_MAP[spriteKey];
    const iconX = startX + i * (BUFF_ICON_SIZE + BUFF_ICON_GAP);
    const iconY = iconBaseY;

    const isDebuff = buff.type === 'dot' || buff.type === 'debuff' || buff.magnitude < 0;

    // Dark backdrop for each icon
    ctx.fillStyle = 'rgba(0, 0, 0, 0.55)';
    ctx.beginPath();
    ctx.roundRect(iconX - 1, iconY - 1, BUFF_ICON_SIZE + 2, BUFF_ICON_SIZE + 2, 2);
    ctx.fill();

    if (sheetReady && region) {
      // Draw sprite icon from sheet
      ctx.drawImage(
        iconImg,
        region.x, region.y, region.w, region.h,
        iconX, iconY, BUFF_ICON_SIZE, BUFF_ICON_SIZE
      );
      // Red tint overlay for debuffs
      if (isDebuff) {
        ctx.fillStyle = 'rgba(255, 40, 40, 0.3)';
        ctx.fillRect(iconX, iconY, BUFF_ICON_SIZE, BUFF_ICON_SIZE);
      }
    } else {
      // Fallback: colored square
      ctx.fillStyle = isDebuff ? 'rgba(200, 50, 50, 0.7)' : 'rgba(50, 150, 50, 0.7)';
      ctx.fillRect(iconX, iconY, BUFF_ICON_SIZE, BUFF_ICON_SIZE);
    }

    // Colored border: red for debuffs, green for buffs
    ctx.strokeStyle = isDebuff ? 'rgba(255, 80, 80, 0.6)' : 'rgba(80, 200, 80, 0.4)';
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.roundRect(iconX - 1, iconY - 1, BUFF_ICON_SIZE + 2, BUFF_ICON_SIZE + 2, 2);
    ctx.stroke();

    // Turn count badge (bottom-right dark circle with white number)
    const turnsLeft = buff.type === 'shield_charges'
      ? buff.charges
      : buff.turns_remaining;
    if (turnsLeft != null && turnsLeft > 0) {
      const badgeX = iconX + BUFF_ICON_SIZE - 1;
      const badgeY = iconY + BUFF_ICON_SIZE - 1;
      ctx.fillStyle = 'rgba(0, 0, 0, 0.75)';
      ctx.beginPath();
      ctx.arc(badgeX, badgeY, 4, 0, Math.PI * 2);
      ctx.fill();
      ctx.fillStyle = '#fff';
      ctx.font = 'bold 6px sans-serif';
      ctx.textAlign = 'center';
      ctx.textBaseline = 'middle';
      ctx.fillText(String(turnsLeft), badgeX, badgeY);
    }
  }

  // Overflow indicator
  if (hasOverflow) {
    const overflowX = startX + MAX_BUFF_ICONS * (BUFF_ICON_SIZE + BUFF_ICON_GAP) + 2;
    ctx.fillStyle = 'rgba(200, 200, 200, 0.7)';
    ctx.font = 'bold 7px sans-serif';
    ctx.textAlign = 'left';
    ctx.textBaseline = 'middle';
    ctx.fillText(`+${activeBuffs.length - MAX_BUFF_ICONS}`, overflowX, iconBaseY + BUFF_ICON_SIZE / 2);
  }
}

// ---------- Phase 14E: Crowd Control Visual Overlays ----------

/**
 * Phase 14E: Draw visual CC indicators directly on units affected by stun, slow, or taunt.
 *
 * - Stun: Rotating gold ⭑ stars orbiting above the unit's head
 * - Slow: Blue ❄ frost marks at the unit's feet with blue tint overlay
 * - Taunt: Red ◆ indicator below the unit showing forced targeting
 *
 * Called per-unit in the render loop for any unit with matching active_buffs entries.
 *
 * @param {CanvasRenderingContext2D} ctx
 * @param {number} x - Tile X (viewport-adjusted)
 * @param {number} y - Tile Y (viewport-adjusted)
 * @param {Array} activeBuffs - The unit's active_buffs array
 * @param {boolean} [isBoss=false]
 */
export function drawCrowdControlIndicators(ctx, x, y, activeBuffs, isBoss = false) {
  if (!activeBuffs || activeBuffs.length === 0) return;

  const cx = x * TILE_SIZE + TILE_SIZE / 2;
  const cy = y * TILE_SIZE + TILE_SIZE / 2 - ELEVATION_OFFSET;
  const radius = isBoss ? TILE_SIZE * 0.42 : TILE_SIZE * 0.35;
  const now = Date.now();

  // --- Check for stun ---
  const hasStun = activeBuffs.some(b => b.type === 'stun');
  if (hasStun) {
    _drawStunStars(ctx, cx, cy, radius, now);
  }

  // --- Check for slow ---
  const hasSlow = activeBuffs.some(b => b.type === 'slow');
  if (hasSlow) {
    _drawSlowFrost(ctx, cx, cy, radius, now);
  }

  // --- Check for taunt ---
  const hasTaunt = activeBuffs.some(b => b.type === 'taunt');
  if (hasTaunt) {
    _drawTauntIndicator(ctx, cx, cy, radius, now);
  }
}

/**
 * Draw 3 rotating gold stars orbiting above the unit's head — classic "stunned" indicator.
 * Stars rotate in a circle with pulsing alpha for a lively feel.
 */
function _drawStunStars(ctx, cx, cy, radius, now) {
  const starCount = 3;
  const orbitRadius = radius * 0.6;
  const orbitY = cy - radius - 16; // Above the nameplate
  const rotationSpeed = 0.002; // radians per ms
  const baseAngle = now * rotationSpeed;
  const pulse = 0.7 + 0.3 * Math.sin(now / 300);

  ctx.save();
  ctx.font = 'bold 10px sans-serif';
  ctx.textAlign = 'center';
  ctx.textBaseline = 'middle';

  for (let i = 0; i < starCount; i++) {
    const angle = baseAngle + (i * Math.PI * 2) / starCount;
    const sx = cx + Math.cos(angle) * orbitRadius;
    const sy = orbitY + Math.sin(angle) * orbitRadius * 0.45; // Flatten orbit for perspective

    // Gold star with pulsing glow
    ctx.fillStyle = `rgba(255, 204, 0, ${pulse})`;
    ctx.strokeStyle = `rgba(255, 238, 85, ${pulse * 0.6})`;
    ctx.lineWidth = 1;

    // Draw a 5-pointed star shape manually for crisp rendering
    _drawStarShape(ctx, sx, sy, 4, 2, 5);
    ctx.fill();
    ctx.stroke();
  }

  ctx.restore();
}

/**
 * Draw a 5-pointed star path at the given center coordinates.
 * @param {CanvasRenderingContext2D} ctx
 * @param {number} cx - Center X
 * @param {number} cy - Center Y
 * @param {number} outerR - Outer radius
 * @param {number} innerR - Inner radius
 * @param {number} points - Number of points
 */
function _drawStarShape(ctx, cx, cy, outerR, innerR, points) {
  ctx.beginPath();
  for (let i = 0; i < points * 2; i++) {
    const r = i % 2 === 0 ? outerR : innerR;
    const a = (Math.PI / 2 * 3) + (i * Math.PI / points);
    const px = cx + Math.cos(a) * r;
    const py = cy + Math.sin(a) * r;
    if (i === 0) ctx.moveTo(px, py);
    else ctx.lineTo(px, py);
  }
  ctx.closePath();
}

/**
 * Draw frost overlay and ice crystal marks near the unit's feet — "slowed" indicator.
 * Blue tint on the tile + small frost marks at the bottom of the unit.
 */
function _drawSlowFrost(ctx, cx, cy, radius, now) {
  const pulse = 0.5 + 0.3 * Math.sin(now / 500);

  ctx.save();

  // Subtle blue tint overlay on the tile
  ctx.fillStyle = `rgba(100, 136, 255, ${0.08 + pulse * 0.06})`;
  const tileLeft = cx - TILE_SIZE / 2;
  const tileTop = cy - TILE_SIZE / 2;
  ctx.fillRect(tileLeft + 2, tileTop + 2, TILE_SIZE - 4, TILE_SIZE - 4);

  // Frost ring at feet
  ctx.strokeStyle = `rgba(100, 160, 255, ${0.3 + pulse * 0.2})`;
  ctx.lineWidth = 1.5;
  ctx.setLineDash([3, 3]);
  ctx.beginPath();
  ctx.ellipse(cx, cy + radius * 0.5, radius * 0.7, radius * 0.3, 0, 0, Math.PI * 2);
  ctx.stroke();
  ctx.setLineDash([]);

  // Small frost crystal characters
  const crystalCount = 3;
  ctx.font = '8px sans-serif';
  ctx.textAlign = 'center';
  ctx.textBaseline = 'middle';
  ctx.fillStyle = `rgba(136, 200, 255, ${0.6 + pulse * 0.3})`;

  for (let i = 0; i < crystalCount; i++) {
    const angle = (i * Math.PI * 2) / crystalCount + now * 0.0005;
    const fx = cx + Math.cos(angle) * radius * 0.55;
    const fy = cy + radius * 0.4 + Math.sin(angle) * radius * 0.2;
    ctx.fillText('❄', fx, fy);
  }

  ctx.restore();
}

/**
 * Draw a red pulsing exclamation mark below the unit — "taunted" indicator.
 * Shows that this unit is forced to target a specific attacker.
 */
function _drawTauntIndicator(ctx, cx, cy, radius, now) {
  const pulse = 0.6 + 0.4 * Math.sin(now / 350);

  ctx.save();

  // Red exclamation mark below the unit
  ctx.font = 'bold 11px sans-serif';
  ctx.textAlign = 'center';
  ctx.textBaseline = 'middle';
  ctx.fillStyle = `rgba(255, 68, 68, ${pulse})`;
  ctx.strokeStyle = `rgba(0, 0, 0, ${pulse * 0.5})`;
  ctx.lineWidth = 2;
  const textY = cy + radius + 12;
  ctx.strokeText('!', cx, textY);
  ctx.fillText('!', cx, textY);

  // Small pulsing red ring around the unit
  ctx.strokeStyle = `rgba(255, 68, 68, ${0.15 + pulse * 0.15})`;
  ctx.lineWidth = 1;
  ctx.beginPath();
  ctx.arc(cx, cy, radius + 3, 0, Math.PI * 2);
  ctx.stroke();

  ctx.restore();
}

/**
 * Phase 7C-3: Draw stance visual indicators for party members on canvas.
 * - Follow: keep stance icons (⇢, ⚔, 🛡, ⚓)
 * - Aggressive: red highlight ring
 * - Defensive: blue shield icon
 * - Hold Position: anchor icon
 */
export function drawStanceIndicators(ctx, partyMembers, players, myPlayerId, ox, oy, visibleTiles, interpolatedPositions = null) {
  const owner = players[myPlayerId];
  if (!owner || !owner.position) return;

  const ownerLerp = interpolatedPositions?.get(myPlayerId);
  const ownerCx = ((ownerLerp ? ownerLerp.x : owner.position.x) - ox) * TILE_SIZE + TILE_SIZE / 2;
  const ownerCy = ((ownerLerp ? ownerLerp.y : owner.position.y) - oy) * TILE_SIZE + TILE_SIZE / 2;

  for (const member of partyMembers) {
    const unit = players[member.unit_id];
    if (!unit || unit.is_alive === false || !unit.position) continue;
    if (unit.extracted) continue; // Phase 12C: Skip extracted heroes
    if (member.unit_id === myPlayerId) continue; // Skip self

    // Skip units outside FOV
    if (visibleTiles && !visibleTiles.has(`${unit.position.x},${unit.position.y}`)) continue;

    const stance = member.ai_stance || 'follow';
    // Phase 15: Use interpolated position for smooth indicator movement
    const unitLerp = interpolatedPositions?.get(member.unit_id);
    const cx = ((unitLerp ? unitLerp.x : unit.position.x) - ox) * TILE_SIZE + TILE_SIZE / 2;
    const cy = ((unitLerp ? unitLerp.y : unit.position.y) - oy) * TILE_SIZE + TILE_SIZE / 2;
    const r = TILE_SIZE * 0.42;

    switch (stance) {
      case 'follow': {
        // Small follow arrow icon below unit (tether line removed)
        ctx.save();
        ctx.fillStyle = 'rgba(100, 200, 255, 0.7)';
        ctx.font = 'bold 8px sans-serif';
        ctx.textAlign = 'center';
        ctx.fillText('⇢', cx, cy + r + 14);
        ctx.restore();
        break;
      }
      case 'aggressive': {
        // Red highlight ring
        ctx.save();
        const pulse = 0.5 + 0.5 * Math.sin(Date.now() / 400);
        ctx.strokeStyle = `rgba(255, 60, 60, ${0.4 + pulse * 0.3})`;
        ctx.lineWidth = 2;
        ctx.beginPath();
        ctx.arc(cx, cy, r + 2, 0, Math.PI * 2);
        ctx.stroke();
        // Small sword icon
        ctx.fillStyle = `rgba(255, 80, 80, ${0.6 + pulse * 0.3})`;
        ctx.font = '9px sans-serif';
        ctx.textAlign = 'center';
        ctx.fillText('⚔', cx, cy + r + 14);
        ctx.restore();
        break;
      }
      case 'defensive': {
        // Blue shield ring
        ctx.save();
        ctx.strokeStyle = 'rgba(80, 140, 255, 0.5)';
        ctx.lineWidth = 2;
        ctx.beginPath();
        ctx.arc(cx, cy, r + 2, 0, Math.PI * 2);
        ctx.stroke();
        // Shield icon
        ctx.fillStyle = 'rgba(80, 140, 255, 0.8)';
        ctx.font = '9px sans-serif';
        ctx.textAlign = 'center';
        ctx.fillText('🛡', cx, cy + r + 14);
        ctx.restore();
        break;
      }
      case 'hold': {
        // Anchor icon — static ring
        ctx.save();
        ctx.strokeStyle = 'rgba(200, 200, 200, 0.4)';
        ctx.lineWidth = 2;
        ctx.setLineDash([2, 2]);
        ctx.beginPath();
        ctx.arc(cx, cy, r + 2, 0, Math.PI * 2);
        ctx.stroke();
        ctx.setLineDash([]);
        // Anchor icon
        ctx.fillStyle = 'rgba(200, 200, 200, 0.8)';
        ctx.font = '9px sans-serif';
        ctx.textAlign = 'center';
        ctx.fillText('⚓', cx, cy + r + 14);
        ctx.restore();
        break;
      }
    }
  }
}

// ---------- Targeting Reticle Revamp: Underfoot Glow + Nameplate Highlight ----------

/**
 * Draw a radial gradient ellipse at the unit's feet, giving a subtle "ground glow"
 * that doesn't overlap with HP bars or nameplates above the sprite.
 *
 * @param {CanvasRenderingContext2D} ctx
 * @param {number} tileX - World tile X
 * @param {number} tileY - World tile Y
 * @param {number} ox - Viewport offset X
 * @param {number} oy - Viewport offset Y
 * @param {{r:number, g:number, b:number}} color - RGB color for the glow
 * @param {number} [intensity=1] - Brightness multiplier (0–1)
 */
export function drawUnderfootGlow(ctx, tileX, tileY, ox, oy, color, intensity = 1) {
  const cx = (tileX - ox) * TILE_SIZE + TILE_SIZE / 2;
  const cy = (tileY - oy) * TILE_SIZE + TILE_SIZE / 1.55;
  // Position the glow slightly below center (at the unit's feet)
  const glowY = cy + TILE_SIZE * 0.12;
  const radiusX = TILE_SIZE * 0.38;
  const radiusY = radiusX * 0.5; // flattened ellipse for ground perspective
  const pulse = 0.7 + 0.3 * Math.sin(Date.now() / 600);
  const alpha = pulse * intensity;

  ctx.save();
  const gradient = ctx.createRadialGradient(cx, glowY, 0, cx, glowY, radiusX);
  gradient.addColorStop(0, `rgba(${color.r}, ${color.g}, ${color.b}, ${0.45 * alpha})`);
  gradient.addColorStop(0.5, `rgba(${color.r}, ${color.g}, ${color.b}, ${0.2 * alpha})`);
  gradient.addColorStop(1, `rgba(${color.r}, ${color.g}, ${color.b}, 0)`);
  ctx.fillStyle = gradient;
  ctx.beginPath();
  ctx.ellipse(cx, glowY, radiusX, radiusY, 0, 0, Math.PI * 2);
  ctx.fill();
  ctx.restore();
}

/**
 * Draw a pulsing glow border around the unit's combined nameplate.
 * Highlights the Diablo-style plate when the unit is selected/targeted.
 *
 * @param {CanvasRenderingContext2D} ctx
 * @param {number} tileX - World tile X
 * @param {number} tileY - World tile Y
 * @param {number} ox - Viewport offset X
 * @param {number} oy - Viewport offset Y
 * @param {{r:number, g:number, b:number}} color - RGB color for the glow
 * @param {string} label - The unit's display name
 * @param {boolean} [isBoss=false]
 * @param {number} [intensity=1] - Brightness multiplier (0–1)
 */
export function drawNameplateGlow(ctx, tileX, tileY, ox, oy, color, label, isBoss = false, intensity = 1, nameplateMode = 'full') {
  if (!label) return;
  const cx = (tileX - ox) * TILE_SIZE + TILE_SIZE / 2;
  const cy = (tileY - oy) * TILE_SIZE + TILE_SIZE / 2;
  const ey = cy - ELEVATION_OFFSET;
  // Use compact rect when in compact mode so glow wraps the smaller plate
  const plate = nameplateMode === 'compact'
    ? _getCompactPlateRect(cx, ey, isBoss)
    : _getPlateRect(cx, ey, isBoss);
  const { plateX, plateY, plateWidth, plateHeight } = plate;

  const pulse = 0.6 + 0.4 * Math.sin(Date.now() / 500);
  const alpha = pulse * intensity;

  ctx.save();

  // Inner glow border on the plate
  ctx.strokeStyle = `rgba(${color.r}, ${color.g}, ${color.b}, ${0.6 * alpha})`;
  ctx.lineWidth = 2;
  ctx.beginPath();
  ctx.roundRect(plateX - 1, plateY - 1, plateWidth + 2, plateHeight + 2, 4);
  ctx.stroke();

  // Outer diffuse glow
  ctx.strokeStyle = `rgba(${color.r}, ${color.g}, ${color.b}, ${0.2 * alpha})`;
  ctx.lineWidth = 4;
  ctx.beginPath();
  ctx.roundRect(plateX - 2, plateY - 2, plateWidth + 4, plateHeight + 4, 5);
  ctx.stroke();

  ctx.restore();
}

/**
 * Composite indicator: draws both underfoot glow and nameplate glow for a
 * selected target. Replaces the old overlapping circle-ring approach.
 *
 * Phase 10G-5 revamp: Uses underfoot glow + pulsing nameplate instead of
 * concentric rings that overlapped with HP bars.
 */
export function drawSelectedTargetIndicator(ctx, tileX, tileY, ox, oy, isEnemy, label = '', isBoss = false) {
  const color = isEnemy
    ? { r: 255, g: 200, b: 50 }   // warm gold for enemies
    : { r: 100, g: 255, b: 120 };  // soft green for allies

  drawUnderfootGlow(ctx, tileX, tileY, ox, oy, color, 1.0);
  drawNameplateGlow(ctx, tileX, tileY, ox, oy, color, label, isBoss, 1.0);
}

/**
 * Phase 10E-1 / 10G-7: Draw a pulsing target reticle (bracket corners) around an auto-targeted unit.
 * Rendered as four corner brackets [ ] that pulse in opacity.
 * Phase 10G-7: Color varies by auto-target type:
 *   - Melee pursuit (no skill): red
 *   - Offensive skill pursuit: orange/amber
 *   - Heal/support skill pursuit: green
 */
export function drawTargetReticle(ctx, tileX, tileY, ox, oy, color = null) {
  const cx = (tileX - ox) * TILE_SIZE + TILE_SIZE / 2;
  const cy = (tileY - oy) * TILE_SIZE + TILE_SIZE / 2;
  const size = TILE_SIZE * 0.48;
  const bracketLen = size * 0.4; // length of each bracket arm
  const pulse = 0.5 + 0.5 * Math.sin(Date.now() / 350);

  // Phase 10G-7: Resolve bracket and glow colors
  const baseColor = color || { r: 255, g: 60, b: 60 }; // default red for melee
  const { r, g, b } = baseColor;

  ctx.save();
  ctx.strokeStyle = `rgba(${r}, ${g}, ${b}, ${0.55 + pulse * 0.45})`;
  ctx.lineWidth = 2;
  ctx.lineCap = 'round';

  // Top-left corner
  ctx.beginPath();
  ctx.moveTo(cx - size, cy - size + bracketLen);
  ctx.lineTo(cx - size, cy - size);
  ctx.lineTo(cx - size + bracketLen, cy - size);
  ctx.stroke();

  // Top-right corner
  ctx.beginPath();
  ctx.moveTo(cx + size - bracketLen, cy - size);
  ctx.lineTo(cx + size, cy - size);
  ctx.lineTo(cx + size, cy - size + bracketLen);
  ctx.stroke();

  // Bottom-right corner
  ctx.beginPath();
  ctx.moveTo(cx + size, cy + size - bracketLen);
  ctx.lineTo(cx + size, cy + size);
  ctx.lineTo(cx + size - bracketLen, cy + size);
  ctx.stroke();

  // Bottom-left corner
  ctx.beginPath();
  ctx.moveTo(cx - size + bracketLen, cy + size);
  ctx.lineTo(cx - size, cy + size);
  ctx.lineTo(cx - size, cy + size - bracketLen);
  ctx.stroke();

  // Subtle outer glow ring
  ctx.strokeStyle = `rgba(${r}, ${g}, ${b}, ${0.15 + pulse * 0.15})`;
  ctx.lineWidth = 1;
  ctx.beginPath();
  ctx.arc(cx, cy, size + 2, 0, Math.PI * 2);
  ctx.stroke();

  ctx.restore();
}

/**
 * Phase 10G-7: Look up a skill definition by ID from available skill data.
 */
export function _findSkillDef(skillId, classSkills, allClassSkills) {
  if (!skillId) return null;
  if (classSkills) {
    const found = classSkills.find(s => s.skill_id === skillId);
    if (found) return found;
  }
  if (allClassSkills) {
    for (const skills of Object.values(allClassSkills)) {
      const found = skills.find(s => s.skill_id === skillId);
      if (found) return found;
    }
  }
  return null;
}
