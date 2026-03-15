/**
 * overlayRenderer — Highlight, preview, and overlay rendering.
 *
 * Extracted from ArenaRenderer.js (P4 refactoring).
 * Handles drawHighlights, drawSkillHighlights, drawQueuePreview,
 * drawHoverPathPreviews, drawGroundItems, drawLootHighlight,
 * drawDamageFloaters, drawSpawnMarker.
 */

import { TILE_SIZE, PREVIEW_COLORS } from './renderConstants.js';

/**
 * Draw highlighted tiles for valid move/attack targets.
 */
export function drawHighlights(ctx, highlights = [], color = 'rgba(74, 159, 245, 0.25)') {
  for (const { x, y } of highlights) {
    ctx.fillStyle = color;
    ctx.fillRect(x * TILE_SIZE + 1, y * TILE_SIZE + 1, TILE_SIZE - 2, TILE_SIZE - 2);
    ctx.strokeStyle = color.replace('0.25', '0.6');
    ctx.lineWidth = 1;
    ctx.strokeRect(x * TILE_SIZE + 1, y * TILE_SIZE + 1, TILE_SIZE - 2, TILE_SIZE - 2);
  }
}

/**
 * Draw skill targeting highlights as corner tick marks instead of filled squares.
 * This keeps the tile center clear so unit sprites, HP bars, and nameplates
 * remain fully readable even on valid-target tiles.
 */
export function drawSkillHighlights(ctx, highlights = [], color = 'rgba(160, 80, 240, 0.7)') {
  for (const { x, y } of highlights) {
    const px = x * TILE_SIZE;
    const py = y * TILE_SIZE;
    const s = TILE_SIZE;
    const inset = 3;     // pixels inset from tile edge
    const tickLen = s * 0.28; // length of each corner tick arm

    // Ultra-subtle fill so the tile is barely tinted
    ctx.fillStyle = 'rgba(160, 80, 240, 0.06)';
    ctx.fillRect(px + 1, py + 1, s - 2, s - 2);

    // Corner tick marks
    ctx.strokeStyle = color;
    ctx.lineWidth = 1.5;
    ctx.lineCap = 'round';

    // Top-left
    ctx.beginPath();
    ctx.moveTo(px + inset, py + inset + tickLen);
    ctx.lineTo(px + inset, py + inset);
    ctx.lineTo(px + inset + tickLen, py + inset);
    ctx.stroke();

    // Top-right
    ctx.beginPath();
    ctx.moveTo(px + s - inset - tickLen, py + inset);
    ctx.lineTo(px + s - inset, py + inset);
    ctx.lineTo(px + s - inset, py + inset + tickLen);
    ctx.stroke();

    // Bottom-right
    ctx.beginPath();
    ctx.moveTo(px + s - inset, py + s - inset - tickLen);
    ctx.lineTo(px + s - inset, py + s - inset);
    ctx.lineTo(px + s - inset - tickLen, py + s - inset);
    ctx.stroke();

    // Bottom-left
    ctx.beginPath();
    ctx.moveTo(px + inset + tickLen, py + s - inset);
    ctx.lineTo(px + inset, py + s - inset);
    ctx.lineTo(px + inset, py + s - inset - tickLen);
    ctx.stroke();
  }
}

/**
 * Draw path preview for queued movement actions with numbered tiles.
 * Shows a connected path with step numbers (1, 2, 3...).
 */
export function drawQueuePreview(ctx, queueTiles = [], playerColor = '#4a9ff5') {
  if (queueTiles.length === 0) return;

  for (let i = 0; i < queueTiles.length; i++) {
    const tile = queueTiles[i];
    const cx = tile.x * TILE_SIZE + TILE_SIZE / 2;
    const cy = tile.y * TILE_SIZE + TILE_SIZE / 2;

    if (tile.type === 'move') {
      // Draw move preview: translucent circle with number
      ctx.fillStyle = 'rgba(74, 159, 245, 0.2)';
      ctx.fillRect(tile.x * TILE_SIZE + 1, tile.y * TILE_SIZE + 1, TILE_SIZE - 2, TILE_SIZE - 2);
      ctx.strokeStyle = 'rgba(74, 159, 245, 0.5)';
      ctx.lineWidth = 1;
      ctx.setLineDash([4, 2]);
      ctx.strokeRect(tile.x * TILE_SIZE + 1, tile.y * TILE_SIZE + 1, TILE_SIZE - 2, TILE_SIZE - 2);
      ctx.setLineDash([]);

      // Draw step number
      ctx.fillStyle = '#8ac4ff';
      ctx.font = 'bold 14px sans-serif';
      ctx.textAlign = 'center';
      ctx.textBaseline = 'middle';
      ctx.fillText(`${i + 1}`, cx, cy);
    } else if (tile.type === 'attack') {
      // Draw melee attack preview: red crosshair
      ctx.fillStyle = 'rgba(245, 74, 74, 0.2)';
      ctx.fillRect(tile.x * TILE_SIZE + 1, tile.y * TILE_SIZE + 1, TILE_SIZE - 2, TILE_SIZE - 2);
      ctx.strokeStyle = 'rgba(245, 74, 74, 0.6)';
      ctx.lineWidth = 1.5;
      // Crosshair lines
      ctx.beginPath();
      ctx.moveTo(cx - 8, cy);
      ctx.lineTo(cx + 8, cy);
      ctx.moveTo(cx, cy - 8);
      ctx.lineTo(cx, cy + 8);
      ctx.stroke();
      // Step number
      ctx.fillStyle = '#ff8888';
      ctx.font = 'bold 10px sans-serif';
      ctx.textAlign = 'center';
      ctx.textBaseline = 'middle';
      ctx.fillText(`${i + 1}`, cx + 10, cy - 10);
    } else if (tile.type === 'ranged_attack') {
      // Draw ranged attack preview: orange/yellow target reticle
      ctx.fillStyle = 'rgba(255, 170, 0, 0.2)';
      ctx.fillRect(tile.x * TILE_SIZE + 1, tile.y * TILE_SIZE + 1, TILE_SIZE - 2, TILE_SIZE - 2);
      ctx.strokeStyle = 'rgba(255, 170, 0, 0.7)';
      ctx.lineWidth = 1.5;
      // Target reticle (circle + crosshair)
      ctx.beginPath();
      ctx.arc(cx, cy, 8, 0, Math.PI * 2);
      ctx.stroke();
      ctx.beginPath();
      ctx.moveTo(cx - 12, cy);
      ctx.lineTo(cx + 12, cy);
      ctx.moveTo(cx, cy - 12);
      ctx.lineTo(cx, cy + 12);
      ctx.stroke();
      // Step number
      ctx.fillStyle = '#ffcc44';
      ctx.font = 'bold 10px sans-serif';
      ctx.textAlign = 'center';
      ctx.textBaseline = 'middle';
      ctx.fillText(`${i + 1}`, cx + 10, cy - 10);
    } else if (tile.type === 'wait') {
      // Draw wait preview: small clock icon placeholder
      ctx.fillStyle = '#aaa';
      ctx.font = '10px sans-serif';
      ctx.textAlign = 'center';
      ctx.textBaseline = 'middle';
      ctx.fillText(`⏳${i + 1}`, cx, cy - 12);
    } else if (tile.type === 'interact') {
      // Draw interact preview: green highlight on door tile
      ctx.fillStyle = 'rgba(139, 69, 19, 0.3)';
      ctx.fillRect(tile.x * TILE_SIZE + 1, tile.y * TILE_SIZE + 1, TILE_SIZE - 2, TILE_SIZE - 2);
      ctx.strokeStyle = 'rgba(139, 69, 19, 0.7)';
      ctx.lineWidth = 2;
      ctx.strokeRect(tile.x * TILE_SIZE + 1, tile.y * TILE_SIZE + 1, TILE_SIZE - 2, TILE_SIZE - 2);
      // Door icon + step number
      ctx.fillStyle = '#DAA520';
      ctx.font = 'bold 10px sans-serif';
      ctx.textAlign = 'center';
      ctx.textBaseline = 'middle';
      ctx.fillText(`🚪${i + 1}`, cx, cy);
    } else if (tile.type === 'skill') {
      // Draw skill cast preview: purple corner ticks + sparkle icon
      ctx.fillStyle = 'rgba(160, 80, 240, 0.12)';
      ctx.fillRect(tile.x * TILE_SIZE + 1, tile.y * TILE_SIZE + 1, TILE_SIZE - 2, TILE_SIZE - 2);
      // Purple sparkle + step number
      ctx.fillStyle = '#c080f0';
      ctx.font = 'bold 10px sans-serif';
      ctx.textAlign = 'center';
      ctx.textBaseline = 'middle';
      ctx.fillText(`✦${i + 1}`, cx, cy);
    }

    // Draw connection line to next tile (for moves)
    if (i < queueTiles.length - 1 && tile.type === 'move') {
      const next = queueTiles[i + 1];
      if (next.type === 'move') {
        const ncx = next.x * TILE_SIZE + TILE_SIZE / 2;
        const ncy = next.y * TILE_SIZE + TILE_SIZE / 2;
        ctx.strokeStyle = 'rgba(74, 159, 245, 0.3)';
        ctx.lineWidth = 2;
        ctx.setLineDash([3, 3]);
        ctx.beginPath();
        ctx.moveTo(cx, cy);
        ctx.lineTo(ncx, ncy);
        ctx.stroke();
        ctx.setLineDash([]);
      }
    }
  }
}

/**
 * Phase 7E-1: Draw hover path previews for all selected units.
 *
 * Renders translucent ghost paths, door interaction icons at door crossings,
 * and ghost unit outlines at each unit's destination (formation preview).
 *
 * @param {CanvasRenderingContext2D} ctx
 * @param {Array<{unitId, path, actions, destTile, intent}>} previews - Per-unit preview data
 * @param {number} ox - Viewport X offset
 * @param {number} oy - Viewport Y offset
 */
export function drawHoverPathPreviews(ctx, previews, ox, oy) {
  if (!previews || previews.length === 0) return;

  for (let i = 0; i < previews.length; i++) {
    const preview = previews[i];
    const colors = PREVIEW_COLORS[i % PREVIEW_COLORS.length];
    const { path, actions, destTile } = preview;

    if (!path || path.length === 0) continue;

    // --- 1. Draw translucent fill on each path tile ---
    for (const step of path) {
      const tx = (step[0] - ox) * TILE_SIZE;
      const ty = (step[1] - oy) * TILE_SIZE;
      ctx.fillStyle = colors.fill;
      ctx.fillRect(tx + 2, ty + 2, TILE_SIZE - 4, TILE_SIZE - 4);
    }

    // --- 2. Draw dashed path line connecting tiles ---
    ctx.strokeStyle = colors.line;
    ctx.lineWidth = 2;
    ctx.setLineDash([6, 4]);
    ctx.beginPath();
    for (let j = 0; j < path.length; j++) {
      const px = (path[j][0] - ox) * TILE_SIZE + TILE_SIZE / 2;
      const py = (path[j][1] - oy) * TILE_SIZE + TILE_SIZE / 2;
      if (j === 0) ctx.moveTo(px, py);
      else ctx.lineTo(px, py);
    }
    ctx.stroke();
    ctx.setLineDash([]);

    // --- 3. Draw small directional dots along the path ---
    for (let j = 0; j < path.length; j++) {
      const px = (path[j][0] - ox) * TILE_SIZE + TILE_SIZE / 2;
      const py = (path[j][1] - oy) * TILE_SIZE + TILE_SIZE / 2;
      ctx.fillStyle = colors.line;
      ctx.beginPath();
      ctx.arc(px, py, 2.5, 0, Math.PI * 2);
      ctx.fill();
    }

    // --- 4. Draw door interaction icons on path ---
    if (actions) {
      for (const action of actions) {
        if (action.action_type === 'interact' && action.target_x != null && action.target_y != null) {
          const dx = (action.target_x - ox) * TILE_SIZE;
          const dy = (action.target_y - oy) * TILE_SIZE;
          const dcx = dx + TILE_SIZE / 2;
          const dcy = dy + TILE_SIZE / 2;

          // Door highlight background
          ctx.fillStyle = 'rgba(139, 69, 19, 0.35)';
          ctx.fillRect(dx + 2, dy + 2, TILE_SIZE - 4, TILE_SIZE - 4);
          ctx.strokeStyle = colors.door;
          ctx.lineWidth = 2;
          ctx.strokeRect(dx + 2, dy + 2, TILE_SIZE - 4, TILE_SIZE - 4);

          // Door icon
          ctx.fillStyle = colors.door;
          ctx.font = 'bold 16px sans-serif';
          ctx.textAlign = 'center';
          ctx.textBaseline = 'middle';
          ctx.fillText('🚪', dcx, dcy);
        }
      }
    }

    // --- 5. Draw ghost outline at destination (formation preview) ---
    if (destTile) {
      const gx = (destTile.x - ox) * TILE_SIZE;
      const gy = (destTile.y - oy) * TILE_SIZE;
      const gcx = gx + TILE_SIZE / 2;
      const gcy = gy + TILE_SIZE / 2;
      const radius = TILE_SIZE * 0.32;

      // Ghost fill circle
      ctx.fillStyle = colors.ghost;
      ctx.beginPath();
      ctx.arc(gcx, gcy, radius, 0, Math.PI * 2);
      ctx.fill();

      // Dashed outline ring
      ctx.strokeStyle = colors.line;
      ctx.lineWidth = 2;
      ctx.setLineDash([3, 3]);
      ctx.beginPath();
      ctx.arc(gcx, gcy, radius, 0, Math.PI * 2);
      ctx.stroke();
      ctx.setLineDash([]);

      // Outer glow ring for formation visibility
      ctx.strokeStyle = colors.fill.replace('0.10', '0.30');
      ctx.lineWidth = 1;
      ctx.beginPath();
      ctx.arc(gcx, gcy, radius + 4, 0, Math.PI * 2);
      ctx.stroke();
    }
  }
}

/**
 * Draw ground item sparkle indicators on tiles that have dropped loot.
 * groundItems: { "x,y": [item, ...] }
 *
 * Phase 16G: Rarity-scaled ground effects:
 *   Common/Uncommon — small gray sparkle
 *   Magic — blue sparkle, slight pulse
 *   Rare — yellow sparkle, moderate pulse, subtle beam
 *   Epic — purple sparkle, strong pulse, visible beam
 *   Unique — orange sparkle, bright beam, screen-edge glow
 *   Set — green sparkle, bright beam, screen-edge glow
 */
export function drawGroundItems(ctx, groundItems, visibleTiles, offsetX = 0, offsetY = 0) {
  if (!groundItems) return;

  const now = Date.now();
  const sparklePhase = (now % 1500) / 1500; // 0-1 cycling for animation
  const fastPhase = (now % 800) / 800;

  for (const [key, items] of Object.entries(groundItems)) {
    if (!items || items.length === 0) continue;
    // Skip tiles not in FOV
    if (visibleTiles && !visibleTiles.has(key)) continue;

    const [xStr, yStr] = key.split(',');
    const x = parseInt(xStr, 10);
    const y = parseInt(yStr, 10);
    const px = (x - offsetX) * TILE_SIZE;
    const py = (y - offsetY) * TILE_SIZE;
    const cx = px + TILE_SIZE / 2;
    const cy = py + TILE_SIZE / 2;

    // Phase 16G: Determine best rarity on the tile for visual effects
    const RARITY_PRIORITY = ['set', 'unique', 'epic', 'rare', 'magic', 'uncommon', 'common'];
    const bestRarity = RARITY_PRIORITY.find(r => items.some(i => i.rarity === r)) || 'common';
    const SPARKLE_COLORS = {
      common:   '#9d9d9d',
      uncommon: '#9d9d9d',
      magic:    '#4488ff',
      rare:     '#ffcc00',
      epic:     '#b040ff',
      unique:   '#ff8800',
      set:      '#00cc44',
    };
    const baseColor = SPARKLE_COLORS[bestRarity] || '#9d9d9d';
    const r = parseInt(baseColor.slice(1, 3), 16);
    const g = parseInt(baseColor.slice(3, 5), 16);
    const b = parseInt(baseColor.slice(5, 7), 16);

    // --- TIER 1: Tile glow (all rarities, intensity scales) ---
    const glowIntensity = bestRarity === 'common' || bestRarity === 'uncommon' ? 0.08
      : bestRarity === 'magic' ? 0.12
      : bestRarity === 'rare' ? 0.18
      : 0.25; // epic/unique/set
    const pulseAmplitude = bestRarity === 'common' || bestRarity === 'uncommon' ? 0.03
      : bestRarity === 'magic' ? 0.06
      : bestRarity === 'rare' ? 0.10
      : 0.15;
    const glowAlpha = glowIntensity + pulseAmplitude * Math.sin(sparklePhase * Math.PI * 2);
    ctx.fillStyle = `rgba(${r},${g},${b},${glowAlpha})`;
    ctx.fillRect(px + 2, py + 2, TILE_SIZE - 4, TILE_SIZE - 4);

    // --- TIER 2: Subtle beam (Rare) ---
    if (bestRarity === 'rare') {
      const beamWidth = 4;
      const beamHeight = TILE_SIZE * 1.5;
      const beamAlpha = 0.15 + 0.10 * Math.sin(sparklePhase * Math.PI * 2);
      const grad = ctx.createLinearGradient(cx, cy - beamHeight, cx, cy);
      grad.addColorStop(0, `rgba(${r},${g},${b},0)`);
      grad.addColorStop(0.4, `rgba(${r},${g},${b},${beamAlpha * 0.4})`);
      grad.addColorStop(1, `rgba(${r},${g},${b},${beamAlpha})`);
      ctx.fillStyle = grad;
      ctx.fillRect(cx - beamWidth / 2, cy - beamHeight, beamWidth, beamHeight);
    }

    // --- TIER 3: Visible beam (Epic) ---
    if (bestRarity === 'epic') {
      const beamWidth = 5;
      const beamHeight = TILE_SIZE * 2;
      const beamAlpha = 0.25 + 0.15 * Math.sin(sparklePhase * Math.PI * 2);
      const grad = ctx.createLinearGradient(cx, cy - beamHeight, cx, cy);
      grad.addColorStop(0, `rgba(${r},${g},${b},0)`);
      grad.addColorStop(0.3, `rgba(${r},${g},${b},${beamAlpha * 0.5})`);
      grad.addColorStop(1, `rgba(${r},${g},${b},${beamAlpha})`);
      ctx.fillStyle = grad;
      ctx.fillRect(cx - beamWidth / 2, cy - beamHeight, beamWidth, beamHeight);
      // Outer glow
      const outerGrad = ctx.createLinearGradient(cx, cy - beamHeight, cx, cy);
      outerGrad.addColorStop(0, `rgba(${r},${g},${b},0)`);
      outerGrad.addColorStop(0.5, `rgba(${r},${g},${b},${beamAlpha * 0.1})`);
      outerGrad.addColorStop(1, `rgba(${r},${g},${b},${beamAlpha * 0.2})`);
      ctx.fillStyle = outerGrad;
      ctx.fillRect(cx - beamWidth * 1.5, cy - beamHeight, beamWidth * 3, beamHeight);
      // Strong pulse at base
      ctx.beginPath();
      ctx.arc(cx, cy, 6 + 2 * Math.sin(fastPhase * Math.PI * 2), 0, Math.PI * 2);
      ctx.fillStyle = `rgba(${r},${g},${b},${beamAlpha * 0.5})`;
      ctx.fill();
    }

    // --- TIER 4: Bright beam + base core (Unique, Set) ---
    if (bestRarity === 'unique' || bestRarity === 'set') {
      const beamWidth = 6;
      const beamHeight = TILE_SIZE * 2.5;
      const beamAlpha = 0.35 + 0.20 * Math.sin(sparklePhase * Math.PI * 2);
      // Main beam
      const grad = ctx.createLinearGradient(cx, cy - beamHeight, cx, cy);
      grad.addColorStop(0, `rgba(${r},${g},${b},0)`);
      grad.addColorStop(0.3, `rgba(${r},${g},${b},${beamAlpha * 0.5})`);
      grad.addColorStop(1, `rgba(${r},${g},${b},${beamAlpha})`);
      ctx.fillStyle = grad;
      ctx.fillRect(cx - beamWidth / 2, cy - beamHeight, beamWidth, beamHeight);
      // Wide outer glow
      const outerGrad = ctx.createLinearGradient(cx, cy - beamHeight, cx, cy);
      outerGrad.addColorStop(0, `rgba(${r},${g},${b},0)`);
      outerGrad.addColorStop(0.5, `rgba(${r},${g},${b},${beamAlpha * 0.15})`);
      outerGrad.addColorStop(1, `rgba(${r},${g},${b},${beamAlpha * 0.25})`);
      ctx.fillStyle = outerGrad;
      ctx.fillRect(cx - beamWidth * 2, cy - beamHeight, beamWidth * 4, beamHeight);
      // Bright core pulse at base
      ctx.beginPath();
      ctx.arc(cx, cy, 8 + 3 * Math.sin(fastPhase * Math.PI * 4), 0, Math.PI * 2);
      ctx.fillStyle = `rgba(${r},${g},${b},${beamAlpha * 0.6})`;
      ctx.fill();
    }

    // Sparkle icon at tile center
    ctx.fillStyle = baseColor;
    ctx.font = 'bold 11px sans-serif';
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';
    ctx.fillText('✦', cx, cy + 10);

    // Item count badge if more than 1
    if (items.length > 1) {
      ctx.fillStyle = '#111';
      ctx.beginPath();
      ctx.arc(px + TILE_SIZE - 8, py + 8, 6, 0, Math.PI * 2);
      ctx.fill();
      ctx.fillStyle = baseColor;
      ctx.font = 'bold 8px sans-serif';
      ctx.fillText(`${items.length}`, px + TILE_SIZE - 8, py + 9);
    }
  }
}

/**
 * Draw a loot highlight on the tile the player is standing on when items are present.
 */
export function drawLootHighlight(ctx, x, y, offsetX = 0, offsetY = 0) {
  const px = (x - offsetX) * TILE_SIZE;
  const py = (y - offsetY) * TILE_SIZE;

  const now = Date.now();
  const pulse = 0.3 + 0.2 * Math.sin((now % 1000) / 1000 * Math.PI * 2);

  ctx.strokeStyle = `rgba(218, 165, 32, ${pulse})`;
  ctx.lineWidth = 2;
  ctx.setLineDash([4, 3]);
  ctx.strokeRect(px + 1, py + 1, TILE_SIZE - 2, TILE_SIZE - 2);
  ctx.setLineDash([]);
}

/**
 * Draw floating damage numbers on the canvas.
 *
 * Phase 14C: Tick floaters (DoT/HoT) render smaller (12px) with a gentler
 * upward drift so the player can visually distinguish periodic ticks from
 * direct skill casts (14px bold).
 */
export function drawDamageFloaters(ctx, floaters = [], offsetX = 0, offsetY = 0) {
  const now = Date.now();
  for (const f of floaters) {
    const age = now - f.createdAt;
    if (age > 1500) continue; // Expire after 1.5s

    const progress = age / 1500;
    const alpha = 1 - progress;

    // Phase 14D: Status floaters (MISS, DODGE, STUNNED, SLOWED, REFLECT) use distinct styling
    const isStatus = !!f.isStatus;
    // Tick floaters drift slower and are smaller
    const isTick = !!f.isTick;

    // Phase 14F: Scale font size by damage magnitude for impactful big hits
    let fontSize;
    let yOffset;
    let displayText = f.text;
    let shakeX = 0;
    if (isStatus) {
      fontSize = 11;
      yOffset = -progress * 25;
    } else if (isTick) {
      fontSize = 12;
      yOffset = -progress * 20;
    } else if (f.damageAmount) {
      // Phase 14F: Scaled font from damage magnitude
      const dmg = f.damageAmount;
      if (f.isKill) {
        fontSize = 16;
        displayText = `☠ ${f.text}`;
        yOffset = -progress * 35;
      } else if (dmg >= 31) {
        fontSize = 18;
        // Slight horizontal shake for massive hits
        shakeX = Math.sin(age * 0.03) * 2 * (1 - progress);
        yOffset = -progress * 35;
      } else if (dmg >= 21) {
        fontSize = 16;
        yOffset = -progress * 32;
      } else if (dmg >= 11) {
        fontSize = 14;
        yOffset = -progress * 30;
      } else {
        fontSize = 12;
        yOffset = -progress * 28;
      }
    } else {
      fontSize = 14;
      yOffset = -progress * 30;
    }

    const cx = (f.x - offsetX) * TILE_SIZE + TILE_SIZE / 2 + shakeX;
    const cy = (f.y - offsetY) * TILE_SIZE + yOffset;

    ctx.globalAlpha = alpha;

    // Phase 14F+: ALL floaters get black stroke outline for readability
    // lineWidth scales with font size — subtle on small text, bold on big hits
    ctx.font = `bold ${fontSize}px sans-serif`;
    ctx.textAlign = 'center';
    ctx.strokeStyle = '#000000';
    ctx.lineWidth = fontSize >= 16 ? 3 : (fontSize >= 14 ? 2.5 : 2);
    ctx.lineJoin = 'round';
    ctx.strokeText(displayText, cx, cy);

    ctx.fillStyle = f.color || '#f44';
    ctx.fillText(displayText, cx, cy);
    ctx.globalAlpha = 1;
  }
}

export function drawSpawnMarker(ctx, x, y) {
  const cx = x * TILE_SIZE + TILE_SIZE / 2;
  const cy = y * TILE_SIZE + TILE_SIZE / 2;

  ctx.strokeStyle = '#333';
  ctx.lineWidth = 1;
  ctx.setLineDash([3, 3]);
  ctx.beginPath();
  ctx.arc(cx, cy, TILE_SIZE * 0.3, 0, Math.PI * 2);
  ctx.stroke();
  ctx.setLineDash([]);
}

// ---------- Loot-System-Overhaul 3.3: ALT-to-Show-Labels ----------

/**
 * Rarity color map for ground item labels (Phase 16C: Diablo-style 6-tier).
 */
const RARITY_COLORS = {
  common:    '#9d9d9d',
  uncommon:  '#9d9d9d',
  magic:     '#4488ff',
  rare:      '#ffcc00',
  epic:      '#b040ff',
  unique:    '#ff8800',
  set:       '#00cc44',
};

/**
 * Draw floating item name labels above all visible ground loot tiles.
 * Called when ALT is held. Multiple items on one tile stack vertically
 * with a slight rightward stagger for clear visual separation.
 *
 * @param {CanvasRenderingContext2D} ctx
 * @param {Object} groundItems - { "x,y": [item, ...] }
 * @param {Set|null} visibleTiles - FOV set of "x,y" strings
 * @param {number} offsetX - Viewport X offset (tile units)
 * @param {number} offsetY - Viewport Y offset (tile units)
 */
export function drawGroundItemLabels(ctx, groundItems, visibleTiles, offsetX = 0, offsetY = 0) {
  if (!groundItems) return;

  const FONT_SIZE = 11;
  const LINE_HEIGHT = 16;        // vertical spacing per label
  const PADDING_X = 5;           // horizontal padding inside label background
  const PADDING_Y = 2;           // vertical padding inside label background
  const STAGGER_X = 6;           // rightward offset per stacked item
  const BORDER_RADIUS = 3;       // rounded corner radius for label bg
  const BASE_OFFSET_Y = -8;      // how far above the tile center the first label starts

  ctx.save();
  ctx.font = `bold ${FONT_SIZE}px sans-serif`;
  ctx.textAlign = 'left';
  ctx.textBaseline = 'middle';

  for (const [key, items] of Object.entries(groundItems)) {
    if (!items || items.length === 0) continue;
    // FOV filter — only show labels on visible tiles
    if (visibleTiles && !visibleTiles.has(key)) continue;

    const [xStr, yStr] = key.split(',');
    const tileX = parseInt(xStr, 10);
    const tileY = parseInt(yStr, 10);

    // Tile center in pixel coordinates
    const tileCX = (tileX - offsetX) * TILE_SIZE + TILE_SIZE / 2;
    const tileCY = (tileY - offsetY) * TILE_SIZE + TILE_SIZE / 2;

    // Draw labels from bottom to top so the first item is closest to the tile
    for (let i = 0; i < items.length; i++) {
      const item = items[i];
      const name = item.name || 'Unknown Item';
      const rarity = item.rarity || 'common';
      const color = RARITY_COLORS[rarity] || RARITY_COLORS.common;

      // Vertical position: stack upward from tile center
      const labelY = tileCY + BASE_OFFSET_Y - (i * LINE_HEIGHT);
      // Horizontal position: stagger right per index
      const labelX = tileCX - 20 + (i * STAGGER_X);

      // Measure text for background
      const textWidth = ctx.measureText(name).width;
      const bgX = labelX - PADDING_X;
      const bgY = labelY - (FONT_SIZE / 2) - PADDING_Y;
      const bgW = textWidth + PADDING_X * 2;
      const bgH = FONT_SIZE + PADDING_Y * 2;

      // Semi-transparent dark background with rounded corners
      ctx.fillStyle = 'rgba(10, 10, 20, 0.82)';
      ctx.beginPath();
      ctx.roundRect(bgX, bgY, bgW, bgH, BORDER_RADIUS);
      ctx.fill();

      // Thin rarity-colored border
      ctx.strokeStyle = color;
      ctx.lineWidth = 1;
      ctx.globalAlpha = 0.6;
      ctx.beginPath();
      ctx.roundRect(bgX, bgY, bgW, bgH, BORDER_RADIUS);
      ctx.stroke();
      ctx.globalAlpha = 1;

      // Item name text in rarity color
      ctx.fillStyle = color;
      ctx.fillText(name, labelX, labelY);
    }
  }

  ctx.restore();
}

// ---------- Phase 23: Persistent AoE Ground Zone Rendering (Miasma, Enfeeble) ----------

/**
 * Draw persistent AoE ground zones — toxic clouds, debuff fields, etc.
 * Each zone renders a pulsing translucent circle with dashed border and
 * animated gas tendrils to communicate the affected area to players.
 *
 * @param {CanvasRenderingContext2D} ctx
 * @param {Array} zones - Array of zone objects: { x, y, radius, turnsRemaining, color, skillId }
 * @param {number} offsetX - Viewport X offset (tile units)
 * @param {number} offsetY - Viewport Y offset (tile units)
 * @param {Set|null} visibleTiles - FOV set of "x,y" strings (null = all visible)
 */
export function drawGroundZones(ctx, zones, offsetX = 0, offsetY = 0, visibleTiles = null) {
  if (!zones || zones.length === 0) return;

  const now = Date.now();
  ctx.save();

  for (const zone of zones) {
    // FOV filter — check center tile visibility
    const key = `${zone.x},${zone.y}`;
    if (visibleTiles && !visibleTiles.has(key)) continue;

    const px = (zone.x - offsetX) * TILE_SIZE;
    const py = (zone.y - offsetY) * TILE_SIZE;
    const cx = px + TILE_SIZE / 2;
    const cy = py + TILE_SIZE / 2;
    const effectRadius = (zone.radius || 2) * TILE_SIZE;

    // Parse hex color to RGB for alpha compositing
    const hex = zone.color || '#50C878';
    const r = parseInt(hex.slice(1, 3), 16);
    const g = parseInt(hex.slice(3, 5), 16);
    const b = parseInt(hex.slice(5, 7), 16);

    // Fade based on remaining turns (last turn fades out)
    const fadeFactor = zone.turnsRemaining <= 1 ? 0.5 : 1.0;

    // --- Pulsing filled circle (area indicator) ---
    const pulse = 1 + 0.03 * Math.sin(now / 700);
    const fillAlpha = 0.06 * fadeFactor;
    ctx.fillStyle = `rgba(${r}, ${g}, ${b}, ${fillAlpha})`;
    ctx.beginPath();
    ctx.arc(cx, cy, effectRadius * pulse, 0, Math.PI * 2);
    ctx.fill();

    // Second layer — slightly smaller, denser fill for depth
    const innerPulse = 1 + 0.05 * Math.sin(now / 500 + 1);
    ctx.fillStyle = `rgba(${r}, ${g}, ${b}, ${fillAlpha * 1.5})`;
    ctx.beginPath();
    ctx.arc(cx, cy, effectRadius * 0.65 * innerPulse, 0, Math.PI * 2);
    ctx.fill();

    // --- Dashed border ring ---
    const borderAlpha = 0.22 * fadeFactor;
    ctx.strokeStyle = `rgba(${r}, ${g}, ${b}, ${borderAlpha})`;
    ctx.lineWidth = 1.5;
    // Rotate the dash pattern over time for a swirling feel
    const dashOffset = (now / 40) % 16;
    ctx.setLineDash([5, 5]);
    ctx.lineDashOffset = dashOffset;
    ctx.beginPath();
    ctx.arc(cx, cy, effectRadius * pulse, 0, Math.PI * 2);
    ctx.stroke();
    ctx.setLineDash([]);
    ctx.lineDashOffset = 0;

    // --- Animated gas wisps (rotating blobs around the perimeter) ---
    const wispCount = 6;
    for (let i = 0; i < wispCount; i++) {
      const angle = (Math.PI * 2 * i / wispCount) + (now / 2000);
      const wispDist = effectRadius * (0.4 + 0.25 * Math.sin(now / 800 + i * 1.3));
      const wx = cx + Math.cos(angle) * wispDist;
      const wy = cy + Math.sin(angle) * wispDist;
      const wispSize = TILE_SIZE * (0.15 + 0.06 * Math.sin(now / 600 + i * 2));
      const wispAlpha = (0.12 + 0.06 * Math.sin(now / 500 + i)) * fadeFactor;

      ctx.fillStyle = `rgba(${r}, ${g}, ${b}, ${wispAlpha})`;
      ctx.beginPath();
      ctx.arc(wx, wy, wispSize, 0, Math.PI * 2);
      ctx.fill();
    }

    // --- Center glow (bright core) ---
    const coreAlpha = (0.08 + 0.04 * Math.sin(now / 400)) * fadeFactor;
    ctx.fillStyle = `rgba(${r}, ${g}, ${b}, ${coreAlpha})`;
    ctx.beginPath();
    ctx.arc(cx, cy, TILE_SIZE * 0.4, 0, Math.PI * 2);
    ctx.fill();

    // --- Duration indicator (small turn count below center) ---
    if (zone.turnsRemaining != null) {
      ctx.fillStyle = `rgba(${r}, ${g}, ${b}, ${0.5 * fadeFactor})`;
      ctx.font = 'bold 9px sans-serif';
      ctx.textAlign = 'center';
      ctx.textBaseline = 'top';
      ctx.fillText(`${zone.turnsRemaining}`, cx, cy + TILE_SIZE * 0.2);
    }
  }

  ctx.restore();
}

// ---------- Phase 26E: Totem Entity Rendering ----------

/**
 * Draw totem entities on the map. Healing totems glow green/amber with a heal radius.
 * Searing totems glow red/orange with a damage radius. Both show HP bars and duration.
 *
 * @param {CanvasRenderingContext2D} ctx
 * @param {Array} totems - Array of totem objects from match state
 * @param {number} offsetX - Viewport X offset (tile units)
 * @param {number} offsetY - Viewport Y offset (tile units)
 * @param {Set|null} visibleTiles - FOV set of "x,y" strings (null = all visible)
 */
export function drawTotems(ctx, totems, offsetX = 0, offsetY = 0, visibleTiles = null) {
  if (!totems || totems.length === 0) return;

  const now = Date.now();
  ctx.save();

  for (const totem of totems) {
    // FOV filter
    const key = `${totem.x},${totem.y}`;
    if (visibleTiles && !visibleTiles.has(key)) continue;

    const px = (totem.x - offsetX) * TILE_SIZE;
    const py = (totem.y - offsetY) * TILE_SIZE;
    const cx = px + TILE_SIZE / 2;
    const cy = py + TILE_SIZE / 2;

    const isHealing = totem.type === 'healing_totem';
    const isEarthgrasp = totem.type === 'earthgrasp_totem';
    const baseColor = isHealing ? '#44cc66' : isEarthgrasp ? '#8B6914' : '#cc4422';
    const glowColor = isHealing ? 'rgba(68, 204, 102, 0.12)' : isEarthgrasp ? 'rgba(139, 105, 20, 0.12)' : 'rgba(204, 68, 34, 0.12)';
    const radiusColor = isHealing ? 'rgba(68, 204, 102, 0.08)' : isEarthgrasp ? 'rgba(139, 105, 20, 0.08)' : 'rgba(204, 68, 34, 0.08)';
    const radiusBorder = isHealing ? 'rgba(68, 204, 102, 0.25)' : isEarthgrasp ? 'rgba(139, 105, 20, 0.25)' : 'rgba(204, 68, 34, 0.25)';

    // --- Effect radius indicator (pulsing circle) ---
    const effectRadius = (totem.effect_radius || 2) * TILE_SIZE;
    const pulse = 1 + 0.04 * Math.sin(now / 600);
    ctx.fillStyle = radiusColor;
    ctx.beginPath();
    ctx.arc(cx, cy, effectRadius * pulse, 0, Math.PI * 2);
    ctx.fill();
    ctx.strokeStyle = radiusBorder;
    ctx.lineWidth = 1;
    ctx.setLineDash([4, 4]);
    ctx.beginPath();
    ctx.arc(cx, cy, effectRadius * pulse, 0, Math.PI * 2);
    ctx.stroke();
    ctx.setLineDash([]);

    // --- Ambient glow under the totem ---
    const glowPulse = 0.5 + 0.2 * Math.sin(now / 400);
    ctx.globalAlpha = glowPulse;
    ctx.fillStyle = glowColor;
    ctx.beginPath();
    ctx.arc(cx, cy, TILE_SIZE * 0.45, 0, Math.PI * 2);
    ctx.fill();
    ctx.globalAlpha = 1;

    // --- Totem body (bone totem pole icon) ---
    const tw = TILE_SIZE * 0.12;
    const th = TILE_SIZE * 0.3;
    ctx.fillStyle = isHealing ? '#c8b87a' : isEarthgrasp ? '#6b5a2a' : '#8a4a2a';
    ctx.strokeStyle = '#222';
    ctx.lineWidth = 1.5;
    ctx.beginPath();
    // Top segment (head)
    ctx.moveTo(cx - tw * 0.7, cy - th);
    ctx.lineTo(cx + tw * 0.7, cy - th);
    ctx.lineTo(cx + tw, cy - th * 0.2);
    // Middle segment
    ctx.lineTo(cx + tw * 1.3, cy - th * 0.2);
    ctx.lineTo(cx + tw * 1.3, cy + th * 0.2);
    // Base segment (wider)
    ctx.lineTo(cx + tw * 1.5, cy + th * 0.2);
    ctx.lineTo(cx + tw * 1.5, cy + th);
    ctx.lineTo(cx - tw * 1.5, cy + th);
    ctx.lineTo(cx - tw * 1.5, cy + th * 0.2);
    ctx.lineTo(cx - tw * 1.3, cy + th * 0.2);
    ctx.lineTo(cx - tw * 1.3, cy - th * 0.2);
    ctx.lineTo(cx - tw, cy - th * 0.2);
    ctx.closePath();
    ctx.fill();
    ctx.stroke();

    // Segment lines
    ctx.strokeStyle = 'rgba(0,0,0,0.25)';
    ctx.lineWidth = 0.8;
    ctx.beginPath();
    ctx.moveTo(cx - tw * 1.3, cy - th * 0.2);
    ctx.lineTo(cx + tw * 1.3, cy - th * 0.2);
    ctx.moveTo(cx - tw * 1.5, cy + th * 0.2);
    ctx.lineTo(cx + tw * 1.5, cy + th * 0.2);
    ctx.stroke();

    // Type indicator glow dot on totem
    ctx.fillStyle = baseColor;
    ctx.beginPath();
    ctx.arc(cx, cy - th * 0.6, tw * 0.5, 0, Math.PI * 2);
    ctx.fill();

    // --- HP bar above totem ---
    const hpRatio = totem.max_hp > 0 ? Math.max(0, totem.hp / totem.max_hp) : 1;
    const barW = TILE_SIZE * 0.6;
    const barH = 3;
    const barX = cx - barW / 2;
    const barY = cy - th - 7;
    ctx.fillStyle = 'rgba(0,0,0,0.6)';
    ctx.fillRect(barX - 1, barY - 1, barW + 2, barH + 2);
    ctx.fillStyle = hpRatio > 0.5 ? '#44cc44' : hpRatio > 0.25 ? '#cccc44' : '#cc4444';
    ctx.fillRect(barX, barY, barW * hpRatio, barH);

    // --- Duration indicator (small number) ---
    if (totem.duration_remaining != null) {
      ctx.fillStyle = baseColor;
      ctx.font = 'bold 9px sans-serif';
      ctx.textAlign = 'center';
      ctx.textBaseline = 'top';
      ctx.fillText(`${totem.duration_remaining}`, cx, cy + th + 2);
    }
  }

  ctx.restore();
}

// ---------- Phase 26E: Root Effect Rendering ----------

/**
 * Draw spectral root effect on rooted units — ghostly chains/hands around feet.
 *
 * @param {CanvasRenderingContext2D} ctx
 * @param {Object} players - All players/units in match
 * @param {number} offsetX - Viewport X offset (tile units)
 * @param {number} offsetY - Viewport Y offset (tile units)
 * @param {Set|null} visibleTiles - FOV set of "x,y" strings
 * @param {Map|null} interpolatedPositions - Smooth position map
 */
export function drawRootEffects(ctx, players, offsetX = 0, offsetY = 0, visibleTiles = null, interpolatedPositions = null) {
  if (!players) return;

  const now = Date.now();
  ctx.save();

  for (const [pid, unit] of Object.entries(players)) {
    if (!unit || unit.is_alive === false || !unit.active_buffs) continue;
    const isRooted = unit.active_buffs.some(b => b.stat === 'rooted');
    if (!isRooted) continue;

    // Get position (use interpolated if available)
    let ux, uy;
    const lerp = interpolatedPositions?.get?.(pid);
    if (lerp) {
      ux = lerp.x;
      uy = lerp.y;
    } else if (unit.position) {
      ux = unit.position.x;
      uy = unit.position.y;
    } else {
      continue;
    }

    // FOV filter
    const key = `${Math.round(ux)},${Math.round(uy)}`;
    if (visibleTiles && !visibleTiles.has(key)) continue;

    const px = (ux - offsetX) * TILE_SIZE;
    const py = (uy - offsetY) * TILE_SIZE;
    const cx = px + TILE_SIZE / 2;
    const cy = py + TILE_SIZE / 2;
    const r = TILE_SIZE * 0.4;

    // Spectral hands/tendrils around feet
    const numTendrils = 5;
    for (let i = 0; i < numTendrils; i++) {
      const angle = (i / numTendrils) * Math.PI * 2 + now / 2000;
      const tendrilR = r * (0.7 + 0.15 * Math.sin(now / 300 + i));
      const tx = cx + Math.cos(angle) * tendrilR;
      const ty = cy + TILE_SIZE * 0.15 + Math.sin(angle) * tendrilR * 0.4;

      ctx.strokeStyle = `rgba(120, 100, 70, ${0.4 + 0.15 * Math.sin(now / 250 + i * 1.3)})`;
      ctx.lineWidth = 2;
      ctx.beginPath();
      ctx.moveTo(cx + Math.cos(angle) * r * 0.2, cy + TILE_SIZE * 0.2);
      ctx.quadraticCurveTo(
        cx + Math.cos(angle + 0.3) * tendrilR * 0.6,
        cy + TILE_SIZE * 0.1,
        tx, ty
      );
      ctx.stroke();
    }

    // Ground ring
    ctx.strokeStyle = 'rgba(100, 80, 50, 0.35)';
    ctx.lineWidth = 1.5;
    ctx.setLineDash([3, 3]);
    ctx.beginPath();
    ctx.ellipse(cx, cy + TILE_SIZE * 0.2, r, r * 0.35, 0, 0, Math.PI * 2);
    ctx.stroke();
    ctx.setLineDash([]);
  }

  ctx.restore();
}

// ---------- Phase 26E: Soul Anchor Buff Rendering ----------

/**
 * Draw soul anchor indicator on anchored units — ethereal anchor glow.
 *
 * @param {CanvasRenderingContext2D} ctx
 * @param {Object} players - All players/units
 * @param {number} offsetX - Viewport X offset
 * @param {number} offsetY - Viewport Y offset
 * @param {Set|null} visibleTiles - FOV set
 * @param {Map|null} interpolatedPositions - Smooth position map
 */
export function drawSoulAnchorEffects(ctx, players, offsetX = 0, offsetY = 0, visibleTiles = null, interpolatedPositions = null) {
  if (!players) return;

  const now = Date.now();
  ctx.save();

  for (const [pid, unit] of Object.entries(players)) {
    if (!unit || unit.is_alive === false || !unit.active_buffs) continue;
    const hasAnchor = unit.active_buffs.some(b => b.stat === 'soul_anchor');
    if (!hasAnchor) continue;

    let ux, uy;
    const lerp = interpolatedPositions?.get?.(pid);
    if (lerp) {
      ux = lerp.x;
      uy = lerp.y;
    } else if (unit.position) {
      ux = unit.position.x;
      uy = unit.position.y;
    } else {
      continue;
    }

    const key = `${Math.round(ux)},${Math.round(uy)}`;
    if (visibleTiles && !visibleTiles.has(key)) continue;

    const px = (ux - offsetX) * TILE_SIZE;
    const py = (uy - offsetY) * TILE_SIZE;
    const cx = px + TILE_SIZE / 2;
    const cy = py + TILE_SIZE / 2;

    // Ghostly anchor symbol above unit
    const anchorPulse = 0.5 + 0.3 * Math.sin(now / 500);
    ctx.globalAlpha = anchorPulse;
    ctx.strokeStyle = '#88ccff';
    ctx.lineWidth = 1.5;
    ctx.fillStyle = 'rgba(136, 204, 255, 0.15)';

    // Draw small anchor icon above unit
    const ax = cx;
    const ay = cy - TILE_SIZE * 0.42;
    const as = 5; // anchor size

    ctx.beginPath();
    // Anchor ring at top
    ctx.arc(ax, ay - as * 1.2, as * 0.4, 0, Math.PI * 2);
    ctx.stroke();
    // Vertical shaft
    ctx.beginPath();
    ctx.moveTo(ax, ay - as * 0.8);
    ctx.lineTo(ax, ay + as * 0.8);
    ctx.stroke();
    // Horizontal bar
    ctx.beginPath();
    ctx.moveTo(ax - as * 0.6, ay - as * 0.2);
    ctx.lineTo(ax + as * 0.6, ay - as * 0.2);
    ctx.stroke();
    // Curved flukes at bottom
    ctx.beginPath();
    ctx.arc(ax - as * 0.4, ay + as * 0.8, as * 0.4, 0, Math.PI, true);
    ctx.stroke();
    ctx.beginPath();
    ctx.arc(ax + as * 0.4, ay + as * 0.8, as * 0.4, 0, Math.PI, true);
    ctx.stroke();

    ctx.globalAlpha = 1;
  }

  ctx.restore();
}
