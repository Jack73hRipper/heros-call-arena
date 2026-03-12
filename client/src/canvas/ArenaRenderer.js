/**
 * ArenaRenderer — Canvas-based grid renderer for the arena.
 *
 * Re-export hub after P4 refactoring. Logic has been extracted into:
 *   - renderConstants.js  — TILE_SIZE, color tables, shape maps
 *   - dungeonRenderer.js  — drawDungeonTiles, drawFog
 *   - unitRenderer.js     — getUnitColor, drawPlayer, drawStanceIndicators,
 *                           drawUnderfootGlow, drawNameplateGlow,
 *                           drawSelectedTargetIndicator, drawTargetReticle, _findSkillDef
 *   - overlayRenderer.js  — drawHighlights, drawSkillHighlights, drawQueuePreview,
 *                           drawHoverPathPreviews, drawGroundItems, drawLootHighlight,
 *                           drawDamageFloaters, drawSpawnMarker
 *
 * Targeting Reticle Revamp: Replaced overlapping circle rings with a layered
 * system — underfoot glow + pulsing nameplate highlight. Priority-based dedup
 * ensures each unit shows at most one indicator type. Skill highlights now use
 * corner tick marks. Hover tile suppressed on indicated units.
 *
 * This file retains: canvas setup, grid, coordinate helpers, renderFrame() orchestrator.
 * All existing importers continue to work unchanged via re-exports.
 */

import { loadSpriteSheet } from './SpriteLoader.js';
import { loadTileSheet, isTileSheetLoaded, drawFloorTile, drawWallTile } from './TileLoader.js';
import { themeEngine, ThemeEngine } from './ThemeEngine.js';

// --- Re-exports from extracted modules (keeps existing import sites working) ---
export { TILE_SIZE, getPlayerColor } from './renderConstants.js';
export { drawDungeonTiles, drawFog, drawPortal, drawChanneling } from './dungeonRenderer.js';
export { getUnitColor, drawPlayer, drawBuffIcons, drawCrowdControlIndicators, drawStanceIndicators, drawUnderfootGlow, drawNameplateGlow, drawSelectedTargetIndicator, drawTargetReticle, drawUnitShadow } from './unitRenderer.js';
export { drawHighlights, drawSkillHighlights, drawQueuePreview, drawHoverPathPreviews, drawGroundItems, drawLootHighlight, drawDamageFloaters, drawSpawnMarker, drawGroundItemLabels, drawTotems, drawGroundZones, drawRootEffects, drawSoulAnchorEffects } from './overlayRenderer.js';
export { themeEngine, ThemeEngine };

// --- Local imports for renderFrame orchestrator ---
import { TILE_SIZE, ENEMY_NAMES } from './renderConstants.js';
import { drawDungeonTiles, drawFog, drawPortal, drawChanneling } from './dungeonRenderer.js';
import { getUnitColor, drawPlayer, drawBuffIcons, drawCrowdControlIndicators, drawStanceIndicators, drawUnderfootGlow, drawNameplateGlow, drawSelectedTargetIndicator, drawTargetReticle, _findSkillDef, drawUnitShadow } from './unitRenderer.js';
import { drawHighlights, drawSkillHighlights, drawQueuePreview, drawHoverPathPreviews, drawGroundItems, drawLootHighlight, drawDamageFloaters, drawGroundItemLabels, drawTotems, drawGroundZones, drawRootEffects, drawSoulAnchorEffects } from './overlayRenderer.js';

// Kick off sprite/tile sheet loading immediately on module import
loadSpriteSheet().catch(() => {
  console.warn('[ArenaRenderer] Sprite sheet unavailable — using shape fallback');
});
loadTileSheet().catch(() => {
  console.warn('[ArenaRenderer] Tile sheet unavailable — using color fallback');
});

// Initialize procedural theme engine with default grimdark theme
// This replaces sprite-based dungeon tiles with procedural canvas rendering.
// Change the theme ID here or call themeEngine.setTheme('id') at runtime.
try {
  themeEngine.setTheme('bleeding_catacombs', TILE_SIZE);
  console.log(`[ArenaRenderer] Theme engine loaded: ${themeEngine.getThemeId()}`);
} catch (e) {
  console.warn('[ArenaRenderer] Theme engine init failed — using sprite/color fallback', e);
}

// ---------- Canvas Setup & Grid (retained in hub) ----------

export function initCanvas(canvasId, gridWidth, gridHeight) {
  const canvas = document.getElementById(canvasId);
  if (!canvas) return null;

  canvas.width = gridWidth * TILE_SIZE;
  canvas.height = gridHeight * TILE_SIZE;

  return canvas.getContext('2d');
}

export function clearCanvas(ctx, gridWidth, gridHeight) {
  ctx.fillStyle = '#0d0d1a';
  ctx.fillRect(0, 0, ctx.canvas.width, ctx.canvas.height);
}

export function drawGrid(ctx, gridWidth, gridHeight, offsetX = 0, offsetY = 0) {
  const canvasW = ctx.canvas.width;
  const canvasH = ctx.canvas.height;
  const tilesVisibleX = Math.ceil(canvasW / TILE_SIZE);
  const tilesVisibleY = Math.ceil(canvasH / TILE_SIZE);
  const startX = offsetX;
  const startY = offsetY;
  const endX = Math.min(gridWidth, startX + tilesVisibleX + 1);
  const endY = Math.min(gridHeight, startY + tilesVisibleY + 1);

  // Draw floor tiles if tile sheet is loaded, then overlay grid lines
  if (isTileSheetLoaded()) {
    for (let x = startX; x < endX; x++) {
      for (let y = startY; y < endY; y++) {
        drawFloorTile(ctx, (x - offsetX) * TILE_SIZE, (y - offsetY) * TILE_SIZE, TILE_SIZE, x, y, 'smooth');
      }
    }
  }

  // Grid lines on top
  ctx.strokeStyle = isTileSheetLoaded() ? 'rgba(0,0,0,0.2)' : '#1a1a33';
  ctx.lineWidth = 1;

  for (let x = startX; x <= endX; x++) {
    const px = (x - offsetX) * TILE_SIZE;
    ctx.beginPath();
    ctx.moveTo(px, 0);
    ctx.lineTo(px, canvasH);
    ctx.stroke();
  }
  for (let y = startY; y <= endY; y++) {
    const py = (y - offsetY) * TILE_SIZE;
    ctx.beginPath();
    ctx.moveTo(0, py);
    ctx.lineTo(canvasW, py);
    ctx.stroke();
  }
}

export function drawObstacle(ctx, x, y) {
  // Try tile sprite first, fall back to solid color
  if (isTileSheetLoaded()) {
    const drawn = drawWallTile(ctx, x * TILE_SIZE, y * TILE_SIZE, TILE_SIZE, x, y, 'stone');
    if (drawn) return;
  }
  ctx.fillStyle = '#2a2a3a';
  ctx.fillRect(x * TILE_SIZE + 1, y * TILE_SIZE + 1, TILE_SIZE - 2, TILE_SIZE - 2);
  ctx.strokeStyle = '#3a3a4a';
  ctx.lineWidth = 1;
  ctx.strokeRect(x * TILE_SIZE + 1, y * TILE_SIZE + 1, TILE_SIZE - 2, TILE_SIZE - 2);
}

// ---------- Coordinate Helpers ----------

/**
 * Convert pixel coordinates to tile coordinates.
 */
export function pixelToTile(px, py) {
  return {
    x: Math.floor(px / TILE_SIZE),
    y: Math.floor(py / TILE_SIZE),
  };
}

/**
 * Draw a single selected/hovered tile outline.
 */
export function drawSelectedTile(ctx, x, y, color = '#e0a040') {
  ctx.strokeStyle = color;
  ctx.lineWidth = 2;
  ctx.strokeRect(x * TILE_SIZE + 1, y * TILE_SIZE + 1, TILE_SIZE - 2, TILE_SIZE - 2);
}

/**
 * Compute viewport offset for centering on a player.
 * Returns { offsetX, offsetY } in tile units.
 * For maps that fit on screen, returns { 0, 0 }.
 */
export function computeViewport(playerX, playerY, gridWidth, gridHeight, canvasWidthPx, canvasHeightPx) {
  const tilesVisibleX = Math.floor(canvasWidthPx / TILE_SIZE);
  const tilesVisibleY = Math.floor(canvasHeightPx / TILE_SIZE);

  // If map fits, no offset
  if (gridWidth <= tilesVisibleX && gridHeight <= tilesVisibleY) {
    return { offsetX: 0, offsetY: 0 };
  }

  // Center around player, clamped to map edges
  let offsetX = Math.round(playerX - tilesVisibleX / 2);
  let offsetY = Math.round(playerY - tilesVisibleY / 2);
  offsetX = Math.max(0, Math.min(offsetX, gridWidth - tilesVisibleX));
  offsetY = Math.max(0, Math.min(offsetY, gridHeight - tilesVisibleY));

  return { offsetX, offsetY };
}

// ---------- Frame Orchestrator ----------

/**
 * Render a complete frame of the arena.
 */
export function renderFrame(ctx, {
  gridWidth, gridHeight, obstacles = [], players = {},
  moveHighlights = [], attackHighlights = [], rangedHighlights = [],
  skillHighlights = [],
  selectedTile = null,
  queuePreviewTiles = [], damageFloaters = [],
  visibleTiles = null, revealedTiles = null, myPlayerId = null, myTeam = null,
  // Dungeon-specific params (4B-2)
  isDungeon = false, tiles = null, tileLegend = null,
  doorStates = {}, chestStates = {},
  viewportOffsetX = 0, viewportOffsetY = 0,
  // Phase 4D-3: Ground items
  groundItems = null,
  lootHighlightTile = null,
  // Party control: active unit highlighting
  activeUnitId = null,
  // Phase 7B-2: All selected unit IDs for multi-select rendering
  selectedUnitIds = [],
  // Phase 7C-3: Party members with stance info for visual indicators
  partyMembers = [],
  // Phase 7E-1: Hover path previews (per-unit ghost paths, door icons, formation ghosts)
  hoverPreviews = null,
  // Phase 10E-1: Auto-target reticle rendering
  autoTargetId = null,
  partyAutoTargets = {},
  // Phase 10G-5: Selected target indicator
  selectedTargetId = null,
  // Phase 10G-7: Skill auto-target info for reticle color differentiation
  autoSkillId = null,
  partyAutoSkills = {},
  allClassSkills = {},
  classSkills = [],
  // Loot-System-Overhaul 3.3: ALT-to-show-labels
  altHeld = false,
  // Phase 12C: Portal scroll rendering
  portal = null,
  channeling = null,
  currentTurn = 0,
  // Phase 15: Interpolated positions for smooth movement (Map<string, {x, y}>)
  interpolatedPositions = null,
  // Phase 26E: Totem entities
  totems = [],
  // Phase 23: Persistent AoE ground zones
  groundZones = [],
}) {
  clearCanvas(ctx, gridWidth, gridHeight);

  const ox = viewportOffsetX;
  const oy = viewportOffsetY;

  if (isDungeon && tiles && tileLegend) {
    // Dungeon rendering path: tile-aware
    drawDungeonTiles(ctx, tiles, tileLegend, doorStates, chestStates, ox, oy);
  } else {
    // Arena rendering path: grid + obstacle blocks
    drawGrid(ctx, gridWidth, gridHeight, ox, oy);
    for (const obs of obstacles) {
      drawObstacle(ctx, obs.x - ox, obs.y - oy);
    }
  }

  // Draw move highlights (blue)
  if (moveHighlights.length > 0) {
    drawHighlights(ctx, moveHighlights.map(t => ({ x: t.x - ox, y: t.y - oy })), 'rgba(74, 159, 245, 0.25)');
  }

  // Draw melee attack highlights (red)
  if (attackHighlights.length > 0) {
    drawHighlights(ctx, attackHighlights.map(t => ({ x: t.x - ox, y: t.y - oy })), 'rgba(245, 74, 74, 0.3)');
  }

  // Draw ranged attack highlights (orange/yellow)
  if (rangedHighlights.length > 0) {
    drawHighlights(ctx, rangedHighlights.map(t => ({ x: t.x - ox, y: t.y - oy })), 'rgba(255, 170, 0, 0.3)');
  }

  // Draw skill targeting highlights (corner-tick marks instead of filled squares)
  if (skillHighlights.length > 0) {
    drawSkillHighlights(ctx, skillHighlights.map(t => ({ x: t.x - ox, y: t.y - oy })));
  }

  // Phase 7E-1: Draw hover path previews (ghost paths, door icons, formation ghosts)
  // Drawn BEFORE committed queue preview so the committed paths appear on top.
  if (hoverPreviews && hoverPreviews.length > 0) {
    drawHoverPathPreviews(ctx, hoverPreviews, ox, oy);
  }

  // Draw queued action path preview (numbered tiles)
  if (queuePreviewTiles.length > 0) {
    drawQueuePreview(ctx, queuePreviewTiles.map(t => ({ ...t, x: t.x - ox, y: t.y - oy })));
  }

  // Draw ground items sparkle (Phase 4D-3)
  if (groundItems) {
    drawGroundItems(ctx, groundItems, visibleTiles, ox, oy);
  }

  // Draw loot highlight on player's tile if items are there
  if (lootHighlightTile) {
    drawLootHighlight(ctx, lootHighlightTile.x, lootHighlightTile.y, ox, oy);
  }

  // Phase 12C: Draw portal entity (after tiles/ground items, before units)
  if (portal) {
    drawPortal(ctx, portal, currentTurn, ox, oy);
  }

  // Phase 23: Draw persistent AoE ground zones (after tiles/ground items, before units)
  if (groundZones && groundZones.length > 0) {
    drawGroundZones(ctx, groundZones, ox, oy, visibleTiles);
  }

  // Phase 26E: Draw totem entities (after tiles/ground items, before units)
  if (totems && totems.length > 0) {
    drawTotems(ctx, totems, ox, oy, visibleTiles);
  }

  // --- Pre-compute auto-target sets (needed for dedup in unit loop and hover suppression) ---
  const allAutoTargets = new Set();
  const autoTargetSkillMap = {};
  if (autoTargetId) {
    allAutoTargets.add(autoTargetId);
    autoTargetSkillMap[autoTargetId] = autoSkillId || null;
  }
  if (partyAutoTargets) {
    for (const [unitId, tid] of Object.entries(partyAutoTargets)) {
      if (tid) {
        allAutoTargets.add(tid);
        autoTargetSkillMap[tid] = partyAutoSkills?.[unitId] || null;
      }
    }
  }

  // Draw selected/hovered tile — suppress on tiles with units that have targeting indicators
  if (selectedTile) {
    let hoverHasIndicator = false;
    // Check if any alive unit on this tile has an active indicator
    for (const [pid, p] of Object.entries(players)) {
      if (p.is_alive !== false && p.position &&
          p.position.x === selectedTile.x && p.position.y === selectedTile.y) {
        if (pid === activeUnitId ||
            (selectedUnitIds && selectedUnitIds.includes(pid)) ||
            pid === selectedTargetId ||
            allAutoTargets.has(pid)) {
          hoverHasIndicator = true;
          break;
        }
      }
    }
    if (!hoverHasIndicator) {
      drawSelectedTile(ctx, selectedTile.x - ox, selectedTile.y - oy);
    }
  }

  // --- Draw players/units — layered: underfoot glow → sprite → nameplate glow ---
  const playerEntries = Object.entries(players);
  playerEntries.forEach(([pid, p], index) => {
    // Phase 12C: Skip extracted heroes — they've entered the portal and are gone
    if (p.extracted) return;

    // If FOV is active, only draw units within visible tiles (always draw self)
    // FOV check uses authoritative integer tile position, not interpolated
    if (visibleTiles && pid !== myPlayerId) {
      if (!visibleTiles.has(`${p.position.x},${p.position.y}`)) {
        return; // Skip — not in FOV
      }
    }

    const color = getUnitColor(pid, p, myPlayerId, myTeam, index);
    // Phase 18E (E1): Use display_name from server for enhanced monsters (rares get generated names,
    // super uniques get fixed names). Fall back to ENEMY_NAMES lookup or username for normals.
    const displayLabel = p.display_name
      || ((p.enemy_type && ENEMY_NAMES[p.enemy_type]) ? ENEMY_NAMES[p.enemy_type] : p.username);

    // Phase 15: Use interpolated (lerped) position for smooth movement, fall back to authoritative
    const lerpPos = interpolatedPositions?.get(pid);
    const drawX = lerpPos ? lerpPos.x : p.position.x;
    const drawY = lerpPos ? lerpPos.y : p.position.y;

    // --- Layer 0: Drop shadow (dark ellipse at ground level, under everything) ---
    if (p.is_alive !== false) {
      drawUnitShadow(ctx, drawX - ox, drawY - oy, p.is_boss || false);
    }

    // --- Determine which indicator type this unit gets (priority system) ---
    // Priority: auto-target reticle > selected target > party selection
    const isPrimary = activeUnitId && pid === activeUnitId;
    const isSecondary = !isPrimary && selectedUnitIds && selectedUnitIds.includes(pid);
    const isSelectedTarget = pid === selectedTargetId && !allAutoTargets.has(pid);
    const hasAutoTarget = allAutoTargets.has(pid);

    // --- Nameplate Declutter: Determine display mode per unit ---
    // "Important" units always get full nameplates; everyone else gets compact HP-bar-only.
    const isMyHero = pid === myPlayerId || partyMembers.some(m => m.unit_id === pid);
    const isImportant = isMyHero
      || isPrimary || isSecondary || isSelectedTarget || hasAutoTarget
      || (p.is_boss)
      || (p.monster_rarity === 'rare')
      || (p.monster_rarity === 'super_unique');
    // Hovered tile check: unit on the tile the mouse is pointing at
    const isHovered = selectedTile
      && p.position
      && p.position.x === selectedTile.x
      && p.position.y === selectedTile.y;
    // Phase B2: Mouse proximity expansion — units within 2 tiles of cursor get full plates
    const NAMEPLATE_PROXIMITY_RADIUS = 2;
    const isNearCursor = selectedTile
      && p.position
      && Math.abs(p.position.x - selectedTile.x) <= NAMEPLATE_PROXIMITY_RADIUS
      && Math.abs(p.position.y - selectedTile.y) <= NAMEPLATE_PROXIMITY_RADIUS;
    // Phase B1: ALT-to-expand all nameplates (same key as ground item labels)
    const nameplateMode = (isImportant || isHovered || isNearCursor || altHeld) ? 'full' : 'compact';

    // --- Layer 1: Underfoot glow (drawn UNDER sprite) ---
    if (p.is_alive !== false && !hasAutoTarget) {
      if (isSelectedTarget) {
        const isEnemy = myTeam && p.team !== myTeam;
        const glowColor = isEnemy
          ? { r: 255, g: 200, b: 50 }
          : { r: 100, g: 255, b: 120 };
        drawUnderfootGlow(ctx, drawX, drawY, ox, oy, glowColor, 1.0);
      } else if (isPrimary) {
        drawUnderfootGlow(ctx, drawX, drawY, ox, oy, { r: 0, g: 230, b: 255 }, 1.0);
      } else if (isSecondary) {
        drawUnderfootGlow(ctx, drawX, drawY, ox, oy, { r: 255, g: 200, b: 50 }, 0.7);
      }
    }

    // --- Layer 2: Unit sprite + combined Diablo-style nameplate ---
    drawPlayer(
      ctx,
      drawX - ox,
      drawY - oy,
      color,
      displayLabel,
      p.hp ?? 100,
      p.max_hp ?? 100,
      p.is_alive !== false,
      p.unit_type || 'human',
      p.class_id || null,
      p.enemy_type || null,
      p.is_boss || false,
      p.sprite_variant || 1,
      pid,
      p.monster_rarity || null,
      p.champion_type || null,
      nameplateMode,
    );

    // Draw buff/debuff icons centered above the nameplate
    if (p.is_alive !== false && p.active_buffs && p.active_buffs.length > 0) {
      drawBuffIcons(ctx, drawX - ox, drawY - oy, p.active_buffs, p.is_boss || false, displayLabel, color, nameplateMode);
    }

    // Phase 14E: Draw crowd control visual overlays (stun stars, slow frost, taunt indicator)
    if (p.is_alive !== false && p.active_buffs && p.active_buffs.length > 0) {
      drawCrowdControlIndicators(ctx, drawX - ox, drawY - oy, p.active_buffs, p.is_boss || false);
    }

    // --- Layer 3: Nameplate glow (drawn OVER sprite, behind nothing but clear of HP bar) ---
    if (p.is_alive !== false && !hasAutoTarget) {
      if (isSelectedTarget) {
        const isEnemy = myTeam && p.team !== myTeam;
        const glowColor = isEnemy
          ? { r: 255, g: 200, b: 50 }
          : { r: 100, g: 255, b: 120 };
        drawNameplateGlow(ctx, drawX, drawY, ox, oy, glowColor, displayLabel, p.is_boss || false, 1.0, nameplateMode);
      } else if (isPrimary) {
        drawNameplateGlow(ctx, drawX, drawY, ox, oy, { r: 0, g: 230, b: 255 }, displayLabel, p.is_boss || false, 1.0, nameplateMode);
      } else if (isSecondary) {
        drawNameplateGlow(ctx, drawX, drawY, ox, oy, { r: 255, g: 200, b: 50 }, displayLabel, p.is_boss || false, 0.7, nameplateMode);
      }
    }
  });

  // Phase 7C-3: Draw stance visual indicators for party members
  if (partyMembers.length > 0 && myPlayerId && players[myPlayerId]) {
    drawStanceIndicators(ctx, partyMembers, players, myPlayerId, ox, oy, visibleTiles, interpolatedPositions);
  }

  // Phase 10E-1 / 10G-7: Draw auto-target reticle on targeted units (color varies by skill type)
  // Auto-target bracket reticle renders ON TOP of sprites — no overlap with underfoot glow
  for (const tid of allAutoTargets) {
    const target = players[tid];
    if (!target || target.is_alive === false || !target.position) continue;
    if (visibleTiles && !visibleTiles.has(`${target.position.x},${target.position.y}`)) continue;

    let reticleColor = null; // null = default red (melee)
    const skillId = autoTargetSkillMap[tid];
    if (skillId) {
      const skillDef = _findSkillDef(skillId, classSkills, allClassSkills);
      if (skillDef?.targeting === 'ally_or_self') {
        reticleColor = { r: 68, g: 255, b: 68 }; // Green for heal/support
      } else {
        reticleColor = { r: 255, g: 170, b: 0 }; // Orange/amber for offensive skills
      }
    }

    // Phase 15: Use interpolated position for smooth reticle tracking
    const reticleLerp = interpolatedPositions?.get(tid);
    const reticleX = reticleLerp ? reticleLerp.x : target.position.x;
    const reticleY = reticleLerp ? reticleLerp.y : target.position.y;
    drawTargetReticle(ctx, reticleX, reticleY, ox, oy, reticleColor);
  }

  // Phase 12C: Draw channeling indicator (after units, before fog)
  if (channeling) {
    drawChanneling(ctx, channeling, players, ox, oy);
  }

  // Phase 26E: Draw root effects on rooted units (after units, before fog)
  drawRootEffects(ctx, players, ox, oy, visibleTiles, interpolatedPositions);

  // Phase 26E: Draw soul anchor indicators on anchored units
  drawSoulAnchorEffects(ctx, players, ox, oy, visibleTiles, interpolatedPositions);

  // Draw FOV fog overlay on top
  if (visibleTiles) {
    drawFog(ctx, gridWidth, gridHeight, visibleTiles, ox, oy, revealedTiles);
  }

  // Loot-System-Overhaul 3.3: Draw ground item labels when ALT is held
  if (altHeld && groundItems) {
    drawGroundItemLabels(ctx, groundItems, visibleTiles, ox, oy);
  }

  // Draw damage floaters on top of everything
  if (damageFloaters.length > 0) {
    drawDamageFloaters(ctx, damageFloaters, ox, oy);
  }

  // Minimap is now rendered on its own dedicated canvas in MinimapPanel component.
  // See client/src/components/MinimapPanel/MinimapPanel.jsx
}
