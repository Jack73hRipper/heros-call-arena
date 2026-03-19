// ─────────────────────────────────────────────────────────
// ThemeEngine.js — Game-side procedural theme renderer
//
// Self-contained Canvas 2D procedural tile drawing engine
// for use in dungeonRenderer.js. Loads theme configs and
// renders tiles using pure canvas operations — no sprites.
//
// Architecture:
//   1. On theme load → pre-render tile variants to offscreen cache
//   2. On draw → blit from cache (fast)
//   3. Special tiles (doors, chests) drawn directly (state-dependent)
//
// Usage in dungeonRenderer.js:
//   import { themeEngine } from './ThemeEngine.js';
//   themeEngine.setTheme('bleeding_catacombs');
//   themeEngine.drawTile(ctx, 'wall', px, py, gridX, gridY);
// ─────────────────────────────────────────────────────────

import { drawChestIcon } from './chestRenderer.js';

// ═══════════════════════════════════════════════════════════
//  NOISE / COLOR UTILITIES
// ═══════════════════════════════════════════════════════════

function cellHash(gridX, gridY, salt = 0) {
  let h = ((gridX * 7919) + (gridY * 6271) + (salt * 3571)) | 0;
  h = ((h >> 16) ^ h) * 0x45d9f3b;
  h = ((h >> 16) ^ h) * 0x45d9f3b;
  h = (h >> 16) ^ h;
  return ((h & 0x7FFFFFFF) >>> 0) / 0x7FFFFFFF;
}

function hexToRgb(hex) {
  const h2 = hex.replace('#', '');
  return {
    r: parseInt(h2.slice(0, 2), 16),
    g: parseInt(h2.slice(2, 4), 16),
    b: parseInt(h2.slice(4, 6), 16),
  };
}

function rgbToCSS(r, g, b, a = 1) {
  if (a < 1) return `rgba(${r}, ${g}, ${b}, ${a})`;
  return `rgb(${r}, ${g}, ${b})`;
}

function varyColor(baseHex, amount, hashVal) {
  const { r, g, b } = hexToRgb(baseHex);
  const shift = Math.floor((hashVal - 0.5) * 2 * amount);
  const clamp = v => Math.max(0, Math.min(255, v + shift));
  return rgbToCSS(clamp(r), clamp(g), clamp(b));
}

function shiftColor(baseHex, amount) {
  const { r, g, b } = hexToRgb(baseHex);
  const clamp = v => Math.max(0, Math.min(255, v + amount));
  return rgbToCSS(clamp(r), clamp(g), clamp(b));
}

function hexAlpha(hex, alpha) {
  const { r, g, b } = hexToRgb(hex);
  return `rgba(${r}, ${g}, ${b}, ${alpha})`;
}

function lerpColor(hexA, hexB, t) {
  const a = hexToRgb(hexA);
  const b = hexToRgb(hexB);
  const mix = (va, vb) => Math.round(va + (vb - va) * t);
  return rgbToCSS(mix(a.r, b.r), mix(a.g, b.g), mix(a.b, b.b));
}

// ═══════════════════════════════════════════════════════════
//  BUILT-IN THEME DEFINITIONS
// ═══════════════════════════════════════════════════════════

const BUILT_IN_THEMES = {
  bleeding_catacombs: {
    id: 'bleeding_catacombs', name: 'Bleeding Catacombs',
    palette: { primary: '#1a1015', secondary: '#2a1520', accent: '#8a2030', mortar: '#4a1525', highlight: '#cc3040', floor: '#3e2d3d', floorAlt: '#413040', grout: '#120a10', furniture: '#4a3520', metal: '#6a5540' },
    wall: { style: 'cracked_stone', brickRows: 3, brickCols: 2, mortarWidth: 2, crackDensity: 0.08, bleedChance: 0.05, edgeVignette: true },
    floor: { style: 'flagstone', slabGrid: 2, groutWidth: 1, stainChance: 0.0, stainColor: 'rgba(120, 20, 20, 0.18)', debrisChance: 0.0, debrisColor: '#4a4040', textureDots: 1 },
    corridor: { style: 'worn_stone', streakChance: 0.0 },
    fog: { exploredTint: 'rgba(30, 10, 15, 0.6)', unexploredColor: '#0a0508' },
    ambient: { vignetteStrength: 0.15, vignetteColor: 'rgba(80, 10, 20, 0.10)', ambientDarkness: 0.40 },
    edge: { style: 'crumble', intensity: 0.6, width: 4 },
    propAffinities: { pillar: 0.6, rubble: 0.4, brazier: 0.8, coffin: 1.0, bookshelf: 0.0, altar: 0.7, puddle: 0.0, barrel: 0.2, chains: 0.8, banner: 0.3, statue: 0.4, throne: 0.3, cage: 0.6, weapon_rack: 0.3, torch_sconce: 0.7, skull_pile: 0.8, mushroom_cluster: 0.1, web: 0.4, fountain: 0.1, candelabra: 0.5, ritual_circle: 0.6, iron_maiden: 0.7, tombstone: 0.5 },
  },
  ashen_undercroft: {
    id: 'ashen_undercroft', name: 'Ashen Undercroft',
    palette: { primary: '#1a1612', secondary: '#2a2218', accent: '#cc6a20', mortar: '#3a2a18', highlight: '#ff8830', floor: '#443a2c', floorAlt: '#473d2f', grout: '#121010', furniture: '#3a2a1a', metal: '#5a5048' },
    wall: { style: 'scorched_brick', brickRows: 3, brickCols: 2, mortarWidth: 2, crackDensity: 0.05, emberChance: 0.06, scorchChance: 0.10, edgeVignette: true },
    floor: { style: 'ash_covered', slabGrid: 2, groutWidth: 1, ashDensity: 0.08, emberChance: 0.0, stainChance: 0.0, stainColor: 'rgba(60, 40, 20, 0.15)', debrisChance: 0.0, debrisColor: '#3a3025' },
    corridor: { style: 'ash_trail', ashDensity: 0.15 },
    fog: { exploredTint: 'rgba(25, 18, 10, 0.6)', unexploredColor: '#0a0805' },
    ambient: { vignetteStrength: 0.14, vignetteColor: 'rgba(80, 50, 10, 0.08)', ambientDarkness: 0.35 },
    edge: { style: 'scorch', intensity: 0.7, width: 4 },
    propAffinities: { pillar: 0.3, rubble: 0.6, brazier: 0.8, coffin: 0.0, bookshelf: 0.0, altar: 0.4, puddle: 0.0, barrel: 0.6, chains: 0.2, banner: 0.2, statue: 0.2, throne: 0.1, cage: 0.3, weapon_rack: 0.5, torch_sconce: 0.8, skull_pile: 0.3, mushroom_cluster: 0.0, web: 0.1, fountain: 0.0, candelabra: 0.4, ritual_circle: 0.2, iron_maiden: 0.3, tombstone: 0.1 },
  },
  drowned_sanctum: {
    id: 'drowned_sanctum', name: 'Drowned Sanctum',
    palette: { primary: '#0a1520', secondary: '#152535', accent: '#2a8a7a', mortar: '#0e1a25', highlight: '#40ccbb', floor: '#24394f', floorAlt: '#273c52', grout: '#080e14', furniture: '#3a4a3a', metal: '#4a5a55' },
    wall: { style: 'mossy_stone', brickRows: 2, brickCols: 2, mortarWidth: 2, crackDensity: 0.04, mossChance: 0.0, waterStainChance: 0.0, veinChance: 0.0, edgeVignette: true },
    floor: { style: 'flooded', slabGrid: 2, groutWidth: 1, waterDepth: 0.08, rippleChance: 0.0, stainChance: 0.0, stainColor: 'rgba(20, 80, 60, 0.12)', debrisChance: 0.0, debrisColor: '#1a3a30' },
    corridor: { style: 'shallow_water', waterDepth: 0.15 },
    fog: { exploredTint: 'rgba(8, 20, 30, 0.6)', unexploredColor: '#040a10' },
    ambient: { vignetteStrength: 0.12, vignetteColor: 'rgba(10, 60, 60, 0.07)', ambientDarkness: 0.38 },
    edge: { style: 'moss_creep', intensity: 0.5, width: 3 },
    propAffinities: { pillar: 0.7, rubble: 0.3, brazier: 0.4, coffin: 0.0, bookshelf: 0.0, altar: 0.5, puddle: 1.0, barrel: 0.1, chains: 0.6, banner: 0.1, statue: 0.5, throne: 0.2, cage: 0.3, weapon_rack: 0.1, torch_sconce: 0.3, skull_pile: 0.2, mushroom_cluster: 0.7, web: 0.3, fountain: 0.8, candelabra: 0.2, ritual_circle: 0.3, iron_maiden: 0.1, tombstone: 0.4 },
  },
  hollowed_cathedral: {
    id: 'hollowed_cathedral', name: 'Hollowed Cathedral',
    palette: { primary: '#1a1525', secondary: '#2a2035', accent: '#6a4a7a', mortar: '#1e1528', highlight: '#aa7a55', floor: '#3d3555', floorAlt: '#403858', grout: '#100e18', furniture: '#4a3830', metal: '#7a6a48' },
    wall: { style: 'carved_stone', brickRows: 2, brickCols: 2, mortarWidth: 3, crackDensity: 0.05, iconChance: 0.0, crumbleChance: 0.05, goldTrimChance: 0.04, edgeVignette: true },
    floor: { style: 'cracked_marble', slabGrid: 3, groutWidth: 1, crackChance: 0.0, veinChance: 0.0, rootChance: 0.0, stainChance: 0.0, stainColor: 'rgba(60, 40, 70, 0.12)', debrisChance: 0.0, debrisColor: '#3a3045' },
    corridor: { style: 'worn_carpet', carpetColor: 'rgba(80, 40, 50, 0.12)' },
    fog: { exploredTint: 'rgba(20, 15, 30, 0.6)', unexploredColor: '#08050e' },
    ambient: { vignetteStrength: 0.15, vignetteColor: 'rgba(50, 30, 60, 0.08)', ambientDarkness: 0.32 },
    edge: { style: 'rubble_strip', intensity: 0.5, width: 4 },
    propAffinities: { pillar: 0.5, rubble: 0.3, brazier: 0.5, coffin: 0.2, bookshelf: 0.8, altar: 0.8, puddle: 0.1, barrel: 0.1, chains: 0.2, banner: 1.0, statue: 0.8, throne: 0.7, cage: 0.1, weapon_rack: 0.2, torch_sconce: 0.6, skull_pile: 0.1, mushroom_cluster: 0.0, web: 0.2, fountain: 0.6, candelabra: 0.9, ritual_circle: 0.4, iron_maiden: 0.1, tombstone: 0.3 },
  },
  iron_depths: {
    id: 'iron_depths', name: 'Iron Depths',
    palette: { primary: '#151518', secondary: '#2a2a30', accent: '#7a5a3a', mortar: '#1a1a20', highlight: '#aa7a4a', floor: '#3e3e48', floorAlt: '#41414b', grout: '#0a0a10', furniture: '#3a3028', metal: '#6a6a72' },
    wall: { style: 'iron_plate', brickRows: 2, brickCols: 2, mortarWidth: 1, crackDensity: 0.03, rivetChance: 0.40, rustChance: 0.08, pipeChance: 0.0, edgeVignette: true },
    floor: { style: 'metal_grate', slabGrid: 2, groutWidth: 2, grateLineSpacing: 10, oilChance: 0.0, stainChance: 0.0, stainColor: 'rgba(90, 60, 30, 0.15)', debrisChance: 0.0, debrisColor: '#3a3530' },
    corridor: { style: 'walkway', railHint: true },
    fog: { exploredTint: 'rgba(15, 15, 20, 0.6)', unexploredColor: '#050508' },
    ambient: { vignetteStrength: 0.14, vignetteColor: 'rgba(40, 40, 50, 0.08)', ambientDarkness: 0.38 },
    edge: { style: 'rust_drip', intensity: 0.6, width: 3 },
    propAffinities: { pillar: 0.7, rubble: 0.3, brazier: 0.5, coffin: 0.1, bookshelf: 0.1, altar: 0.3, puddle: 0.2, barrel: 0.7, chains: 0.9, banner: 0.2, statue: 0.2, throne: 0.1, cage: 0.8, weapon_rack: 0.7, torch_sconce: 0.6, skull_pile: 0.2, mushroom_cluster: 0.0, web: 0.2, fountain: 0.1, candelabra: 0.3, ritual_circle: 0.1, iron_maiden: 0.8, tombstone: 0.1 },
  },
  forgotten_cellar: {
    id: 'forgotten_cellar', name: 'Forgotten Cellar',
    palette: { primary: '#18160f', secondary: '#2c2820', accent: '#4a4035', mortar: '#1e1c15', highlight: '#6a6050', floor: '#443c30', floorAlt: '#473f33', grout: '#100e0a', furniture: '#5a4a35', metal: '#5a4a3a' },
    wall: { style: 'rough_hewn', brickRows: 3, mortarWidth: 2 },
    floor: { style: 'packed_earth' },
    corridor: { style: 'worn_stone', streakChance: 0.0 },
    fog: { exploredTint: 'rgba(20, 18, 12, 0.55)', unexploredColor: '#0a0908' },
    ambient: { vignetteStrength: 0.08, vignetteColor: 'rgba(30, 25, 15, 0.05)', ambientDarkness: 0.30 },
    edge: { style: 'dust_drift', intensity: 0.4, width: 2 },
    propAffinities: { pillar: 0.4, rubble: 0.7, brazier: 0.7, coffin: 0.0, bookshelf: 0.0, altar: 0.3, puddle: 0.1, barrel: 0.9, chains: 0.3, banner: 0.1, statue: 0.1, throne: 0.0, cage: 0.2, weapon_rack: 0.4, torch_sconce: 0.7, skull_pile: 0.1, mushroom_cluster: 0.3, web: 0.6, fountain: 0.0, candelabra: 0.2, ritual_circle: 0.0, iron_maiden: 0.1, tombstone: 0.1 },
  },
  pale_ossuary: {
    id: 'pale_ossuary', name: 'Pale Ossuary',
    palette: { primary: '#1c1a1e', secondary: '#35323a', accent: '#504a55', mortar: '#28262c', highlight: '#807580', floor: '#4d4856', floorAlt: '#504b59', grout: '#141218', furniture: '#4a4540', metal: '#6a6570' },
    wall: { style: 'bone_stack', boneRows: 4, seamWidth: 1 },
    floor: { style: 'polished_slab', slabGrid: 2, groutWidth: 1 },
    corridor: { style: 'worn_carpet', carpetColor: 'rgba(60, 55, 65, 0.08)' },
    fog: { exploredTint: 'rgba(20, 18, 24, 0.55)', unexploredColor: '#08060c' },
    ambient: { vignetteStrength: 0.06, vignetteColor: 'rgba(40, 35, 50, 0.04)', ambientDarkness: 0.30 },
    edge: { style: 'clean_edge', intensity: 0.3, width: 1 },
    propAffinities: { pillar: 0.6, rubble: 0.2, brazier: 0.4, coffin: 0.9, bookshelf: 0.1, altar: 0.8, puddle: 0.1, barrel: 0.2, chains: 0.5, banner: 0.3, statue: 0.6, throne: 0.4, cage: 0.3, weapon_rack: 0.1, torch_sconce: 0.5, skull_pile: 1.0, mushroom_cluster: 0.0, web: 0.3, fountain: 0.3, candelabra: 0.7, ritual_circle: 0.5, iron_maiden: 0.4, tombstone: 0.8 },
  },
  silent_vault: {
    id: 'silent_vault', name: 'Silent Vault',
    palette: { primary: '#101520', secondary: '#1e2535', accent: '#3a4a5a', mortar: '#151a28', highlight: '#5a6a80', floor: '#2e3c50', floorAlt: '#313f53', grout: '#0a0e15', furniture: '#3a3040', metal: '#5a6068' },
    wall: { style: 'ashlar_block', blockRows: 3, blockCols: 2, mortarWidth: 1 },
    floor: { style: 'dusty_tile', slabGrid: 3, groutWidth: 1 },
    corridor: { style: 'shallow_water', waterDepth: 0.04 },
    fog: { exploredTint: 'rgba(10, 15, 25, 0.55)', unexploredColor: '#060810' },
    ambient: { vignetteStrength: 0.06, vignetteColor: 'rgba(20, 30, 50, 0.04)', ambientDarkness: 0.35 },
    edge: { style: 'seam_line', intensity: 0.4, width: 1 },
    propAffinities: { pillar: 0.8, rubble: 0.2, brazier: 0.3, coffin: 0.1, bookshelf: 0.9, altar: 0.5, puddle: 0.0, barrel: 0.3, chains: 0.2, banner: 0.7, statue: 0.6, throne: 0.5, cage: 0.1, weapon_rack: 0.2, torch_sconce: 0.5, skull_pile: 0.1, mushroom_cluster: 0.0, web: 0.3, fountain: 0.4, candelabra: 0.7, ritual_circle: 0.3, iron_maiden: 0.0, tombstone: 0.2 },
  },
  fungal_grotto: {
    id: 'fungal_grotto', name: 'Fungal Grotto',
    palette: { primary: '#121a10', secondary: '#1e2a18', accent: '#5aaa40', mortar: '#0e1a0c', highlight: '#80ee60', floor: '#2a3822', floorAlt: '#2d3b25', grout: '#0a100a', furniture: '#3a4520', metal: '#4a6a45' },
    wall: { style: 'fungal_growth' },
    floor: { style: 'mycelium_mat' },
    corridor: { style: 'shallow_water', waterDepth: 0.06 },
    fog: { exploredTint: 'rgba(10, 20, 8, 0.55)', unexploredColor: '#060a05' },
    ambient: { vignetteStrength: 0.12, vignetteColor: 'rgba(30, 60, 15, 0.08)', ambientDarkness: 0.40 },
    edge: { style: 'spore_creep', intensity: 0.7, width: 5 },
    propAffinities: { pillar: 0.4, rubble: 0.5, brazier: 0.3, coffin: 0.0, bookshelf: 0.0, altar: 0.4, puddle: 0.8, barrel: 0.3, chains: 0.2, banner: 0.0, statue: 0.2, throne: 0.0, cage: 0.1, weapon_rack: 0.1, torch_sconce: 0.2, skull_pile: 0.3, mushroom_cluster: 1.0, web: 0.7, fountain: 0.3, candelabra: 0.1, ritual_circle: 0.2, iron_maiden: 0.0, tombstone: 0.2 },
  },
  frozen_crypt: {
    id: 'frozen_crypt', name: 'Frozen Crypt',
    palette: { primary: '#0a1020', secondary: '#182838', accent: '#4488cc', mortar: '#101828', highlight: '#88ccff', floor: '#253a4e', floorAlt: '#283d51', grout: '#080e18', furniture: '#4a4848', metal: '#6a7a88' },
    wall: { style: 'ice_crystal' },
    floor: { style: 'frozen_stone', slabGrid: 2, groutWidth: 1 },
    corridor: { style: 'shallow_water', waterDepth: 0.08 },
    fog: { exploredTint: 'rgba(8, 12, 25, 0.55)', unexploredColor: '#040610' },
    ambient: { vignetteStrength: 0.10, vignetteColor: 'rgba(20, 40, 80, 0.06)', ambientDarkness: 0.35 },
    edge: { style: 'frost_creep', intensity: 0.8, width: 6 },
    propAffinities: { pillar: 0.7, rubble: 0.4, brazier: 0.2, coffin: 0.3, bookshelf: 0.0, altar: 0.5, puddle: 0.0, barrel: 0.2, chains: 0.6, banner: 0.3, statue: 0.5, throne: 0.3, cage: 0.4, weapon_rack: 0.3, torch_sconce: 0.4, skull_pile: 0.4, mushroom_cluster: 0.0, web: 0.2, fountain: 0.2, candelabra: 0.4, ritual_circle: 0.3, iron_maiden: 0.3, tombstone: 0.6 },
  },
  cursed_shrine: {
    id: 'cursed_shrine', name: 'Cursed Shrine',
    palette: { primary: '#1a0a10', secondary: '#2a1520', accent: '#cc4430', mortar: '#200a12', highlight: '#ffaa30', floor: '#3a2028', floorAlt: '#3d232b', grout: '#100810', furniture: '#4a2520', metal: '#5a3a38' },
    wall: { style: 'blood_stone', blockRows: 2, blockCols: 2, mortarWidth: 2 },
    floor: { style: 'ritual_tile', slabGrid: 3, groutWidth: 1 },
    corridor: { style: 'worn_carpet', carpetColor: 'rgba(120, 30, 30, 0.12)' },
    fog: { exploredTint: 'rgba(25, 8, 12, 0.6)', unexploredColor: '#0a0408' },
    ambient: { vignetteStrength: 0.16, vignetteColor: 'rgba(100, 20, 15, 0.10)', ambientDarkness: 0.42 },
    edge: { style: 'blood_seep', intensity: 0.6, width: 4 },
    propAffinities: { pillar: 0.5, rubble: 0.3, brazier: 0.8, coffin: 0.4, bookshelf: 0.2, altar: 1.0, puddle: 0.0, barrel: 0.1, chains: 0.7, banner: 0.9, statue: 0.6, throne: 0.5, cage: 0.5, weapon_rack: 0.3, torch_sconce: 0.7, skull_pile: 0.6, mushroom_cluster: 0.0, web: 0.3, fountain: 0.2, candelabra: 0.8, ritual_circle: 1.0, iron_maiden: 0.5, tombstone: 0.4 },
  },
};

// ═══════════════════════════════════════════════════════════
//  WALL DRAWING FUNCTIONS
// ═══════════════════════════════════════════════════════════

function drawWall_crackedStone(ctx, x, y, size, seed, pal, p) {
  const h = cellHash;
  ctx.fillStyle = pal.primary;
  ctx.fillRect(x, y, size, size);
  const bH = size / (p.brickRows || 3), bW = size / (p.brickCols || 2), mw = p.mortarWidth || 2;
  for (let r = 0; r < (p.brickRows || 3); r++) {
    const off = (r % 2 === 0) ? 0 : bW * 0.5;
    for (let c = -1; c <= (p.brickCols || 2); c++) {
      const bx = x + off + c * bW, by = y + r * bH;
      const dX = Math.max(x + mw, bx + mw), dY = by + mw;
      const dR = Math.min(x + size - mw, bx + bW - mw), dB = by + bH - mw;
      const dW = dR - dX, dH = dB - dY;
      if (dW <= 2 || dH <= 2) continue;
      const v = h(r * 10 + c, seed, 1);
      ctx.fillStyle = varyColor(pal.secondary, 12, v);
      ctx.fillRect(dX, dY, dW, dH);
      ctx.fillStyle = shiftColor(pal.secondary, 8); ctx.fillRect(dX, dY, dW, 1);
      ctx.fillStyle = shiftColor(pal.primary, -5); ctx.fillRect(dX, dY + dH - 1, dW, 1);
      ctx.fillStyle = shiftColor(pal.secondary, 4); ctx.fillRect(dX, dY + 1, 1, dH - 2);
    }
  }
  ctx.fillStyle = pal.mortar;
  for (let r = 1; r < (p.brickRows || 3); r++) {
    ctx.fillRect(x, y + r * bH - 1, size, mw);
    if (h(r, seed, 20) < (p.bleedChance || 0.05)) {
      ctx.fillStyle = hexAlpha(pal.accent, 0.4);
      ctx.fillRect(x + h(r, seed, 21) * (size - 12), y + r * bH - 1, 8 + h(r, seed, 22) * 6, mw);
      ctx.fillStyle = pal.mortar;
    }
  }
  if (h(0, seed, 30) < (p.crackDensity || 0.08)) {
    ctx.strokeStyle = hexAlpha(pal.accent, 0.5); ctx.lineWidth = 0.8; ctx.beginPath();
    const cx2 = x + size * (0.2 + h(0, seed, 31) * 0.6), cy2 = y + size * (0.2 + h(0, seed, 32) * 0.6);
    ctx.moveTo(cx2, cy2);
    for (let s = 0; s < 2 + Math.floor(h(0, seed, 33) * 3); s++) ctx.lineTo(cx2 + (h(s, seed, 34) - 0.5) * size * 0.5, cy2 + h(s, seed, 35) * size * 0.4);
    ctx.stroke();
  }
  if (p.edgeVignette) _edgeVig(ctx, x, y, size);
}

function drawWall_scorchedBrick(ctx, x, y, size, seed, pal, p) {
  const h = cellHash;
  ctx.fillStyle = pal.primary; ctx.fillRect(x, y, size, size);
  const bH = size / (p.brickRows || 3), bW = size / (p.brickCols || 2), mw = p.mortarWidth || 2;
  for (let r = 0; r < (p.brickRows || 3); r++) {
    const off = (r % 2 === 0) ? 0 : bW * 0.45;
    for (let c = -1; c <= (p.brickCols || 2); c++) {
      const bx = x + off + c * bW, by = y + r * bH;
      const dX = Math.max(x + mw, bx + mw), dY = by + mw, dR = Math.min(x + size - mw, bx + bW - mw), dB = by + bH - mw;
      const dW = dR - dX, dH = dB - dY;
      if (dW <= 2 || dH <= 2) continue;
      ctx.fillStyle = varyColor(pal.secondary, 10, h(r * 10 + c, seed, 1)); ctx.fillRect(dX, dY, dW, dH);
      if (h(r * 10 + c, seed, 5) < (p.scorchChance || 0.10)) { ctx.fillStyle = 'rgba(0,0,0,0.3)'; ctx.fillRect(dX, dY, dW, dH); }
      ctx.fillStyle = shiftColor(pal.secondary, 6); ctx.fillRect(dX, dY, dW, 1);
    }
  }
  for (let r = 1; r < (p.brickRows || 3); r++) {
    ctx.fillStyle = pal.mortar; ctx.fillRect(x, y + r * bH - 1, size, mw);
    if (h(r, seed, 20) < (p.emberChance || 0.06)) {
      const gx = x + h(r, seed, 21) * (size - 10), gw = 6 + h(r, seed, 22) * 8;
      ctx.fillStyle = hexAlpha(pal.accent, 0.6); ctx.fillRect(gx, y + r * bH - 1, gw, mw);
      ctx.fillStyle = hexAlpha(pal.highlight, 0.3); ctx.fillRect(gx + 2, y + r * bH - 1, gw - 4, mw);
    }
  }
  if (p.edgeVignette) _edgeVig(ctx, x, y, size);
}

function drawWall_mossyStone(ctx, x, y, size, seed, pal, p) {
  const h = cellHash;
  ctx.fillStyle = pal.primary; ctx.fillRect(x, y, size, size);
  const bH = size / (p.brickRows || 2), bW = size / (p.brickCols || 2), mw = p.mortarWidth || 2;
  for (let r = 0; r < (p.brickRows || 2); r++) {
    const off = (r % 2 === 0) ? 0 : bW * 0.35;
    for (let c = -1; c <= (p.brickCols || 2); c++) {
      const bx = x + off + c * bW, by = y + r * bH;
      const dX = Math.max(x + mw, bx + mw), dY = by + mw, dR = Math.min(x + size - mw, bx + bW - mw), dB = by + bH - mw;
      const dW = dR - dX, dH = dB - dY;
      if (dW <= 2 || dH <= 2) continue;
      ctx.fillStyle = varyColor(pal.secondary, 8, h(r * 10 + c, seed, 1)); ctx.fillRect(dX, dY, dW, dH);
      ctx.fillStyle = shiftColor(pal.secondary, 5); ctx.fillRect(dX, dY, dW, 2);
      if (h(r * 10 + c, seed, 10) < (p.mossChance || 0.0)) {
        ctx.fillStyle = hexAlpha(pal.accent, 0.4); ctx.beginPath();
        ctx.arc(dX + h(r * 10 + c, seed, 11) * (dW - 8) + 4, dY + h(r * 10 + c, seed, 12) * (dH - 6) + 3, 3 + h(r + c, seed, 13) * 3, 0, Math.PI * 2);
        ctx.fill();
      }
    }
  }
  if (h(0, seed, 40) < (p.waterStainChance || 0.0)) {
    const sx = x + 4 + h(0, seed, 41) * (size - 8);
    ctx.fillStyle = shiftColor(pal.primary, -8); ctx.fillRect(sx, y, 2, size);
  }
  if (h(0, seed, 50) < (p.veinChance || 0.0)) {
    ctx.strokeStyle = hexAlpha(pal.highlight, 0.35); ctx.lineWidth = 1; ctx.beginPath();
    const vx = x + h(0, seed, 51) * size * 0.6 + size * 0.2;
    ctx.moveTo(vx, y + 2);
    ctx.bezierCurveTo(vx + (h(0, seed, 52) - 0.5) * 10, y + size * 0.3, vx + (h(0, seed, 53) - 0.5) * 12, y + size * 0.7, vx + (h(0, seed, 54) - 0.5) * 8, y + size - 2);
    ctx.stroke(); ctx.strokeStyle = hexAlpha(pal.accent, 0.12); ctx.lineWidth = 3; ctx.stroke();
  }
  ctx.fillStyle = pal.mortar;
  for (let r = 1; r < (p.brickRows || 2); r++) ctx.fillRect(x, y + r * bH - 1, size, mw);
  if (p.edgeVignette) _edgeVig(ctx, x, y, size);
}

function drawWall_carvedStone(ctx, x, y, size, seed, pal, p) {
  const h = cellHash;
  ctx.fillStyle = pal.primary; ctx.fillRect(x, y, size, size);
  const bH = size / (p.brickRows || 2), bW = size / (p.brickCols || 2), mw = p.mortarWidth || 3;
  for (let r = 0; r < (p.brickRows || 2); r++) {
    for (let c = 0; c < (p.brickCols || 2); c++) {
      const bx = x + c * bW + mw, by = y + r * bH + mw, bw = bW - mw * 2, bh = bH - mw * 2;
      if (bw <= 2 || bh <= 2) continue;
      ctx.fillStyle = varyColor(pal.secondary, 10, h(r * 10 + c, seed, 1)); ctx.fillRect(bx, by, bw, bh);
      ctx.strokeStyle = shiftColor(pal.secondary, 12); ctx.lineWidth = 0.8; ctx.strokeRect(bx + 3, by + 3, bw - 6, bh - 6);
      if (h(r * 10 + c, seed, 15) < (p.crumbleChance || 0.05)) {
        const cn = Math.floor(h(r * 10 + c, seed, 16) * 4);
        ctx.fillStyle = pal.primary; ctx.fillRect(cn < 2 ? bx : bx + bw - 6, cn % 2 === 0 ? by : by + bh - 5, 5 + h(r + c, seed, 17) * 3, 4 + h(r + c, seed, 18) * 3);
      }
      if (h(r * 10 + c, seed, 20) < (p.iconChance || 0.0)) {
        ctx.strokeStyle = hexAlpha(pal.accent, 0.25); ctx.lineWidth = 1;
        const icx = bx + bw / 2, icy = by + bh / 2, it = Math.floor(h(r * 10 + c, seed, 21) * 3);
        ctx.beginPath();
        if (it === 0) { ctx.moveTo(icx, icy - 5); ctx.lineTo(icx, icy + 5); ctx.moveTo(icx - 4, icy - 1); ctx.lineTo(icx + 4, icy - 1); }
        else if (it === 1) { ctx.arc(icx, icy, 4, 0, Math.PI * 2); }
        else { ctx.moveTo(icx, icy - 5); ctx.lineTo(icx - 4, icy + 4); ctx.lineTo(icx + 4, icy + 4); ctx.closePath(); }
        ctx.stroke();
      }
    }
  }
  if (h(0, seed, 30) < (p.goldTrimChance || 0.04)) { ctx.fillStyle = hexAlpha(pal.highlight, 0.25); ctx.fillRect(x + 4, y + bH - 1, size - 8, 1); }
  ctx.fillStyle = pal.mortar;
  for (let r = 1; r < (p.brickRows || 2); r++) ctx.fillRect(x, y + r * bH - 1, size, mw);
  for (let c = 1; c < (p.brickCols || 2); c++) ctx.fillRect(x + c * bW - 1, y, mw, size);
  if (p.edgeVignette) _edgeVig(ctx, x, y, size);
}

function drawWall_ironPlate(ctx, x, y, size, seed, pal, p) {
  const h = cellHash;
  ctx.fillStyle = pal.primary; ctx.fillRect(x, y, size, size);
  const pH = size / (p.brickRows || 2), pW = size / (p.brickCols || 2), mw = p.mortarWidth || 1;
  for (let r = 0; r < (p.brickRows || 2); r++) {
    for (let c = 0; c < (p.brickCols || 2); c++) {
      const px2 = x + c * pW + mw, py2 = y + r * pH + mw, pw = pW - mw * 2, ph = pH - mw * 2;
      if (pw <= 2 || ph <= 2) continue;
      ctx.fillStyle = varyColor(pal.secondary, 8, h(r * 10 + c, seed, 1)); ctx.fillRect(px2, py2, pw, ph);
      ctx.fillStyle = shiftColor(pal.secondary, 5); ctx.fillRect(px2 + 2, py2 + ph * 0.3, pw - 4, ph * 0.15);
      ctx.fillStyle = shiftColor(pal.secondary, 10); ctx.fillRect(px2, py2, pw, 1);
      ctx.fillStyle = shiftColor(pal.primary, -5); ctx.fillRect(px2, py2 + ph - 1, pw, 1);
      if (h(r * 10 + c, seed, 10) < (p.rivetChance || 0.40)) {
        _rivet(ctx, px2 + 3, py2 + 3, pal); _rivet(ctx, px2 + pw - 4, py2 + 3, pal);
        _rivet(ctx, px2 + 3, py2 + ph - 4, pal); _rivet(ctx, px2 + pw - 4, py2 + ph - 4, pal);
      }
      if (h(r * 10 + c, seed, 20) < (p.rustChance || 0.08)) {
        ctx.fillStyle = hexAlpha(pal.accent, 0.35);
        const rx = px2 + h(r + c, seed, 21) * (pw - 6), rw = 3 + h(r + c, seed, 22) * 4, rh = ph * (0.4 + h(r + c, seed, 23) * 0.5);
        ctx.fillRect(rx, py2 + 2, rw, rh);
      }
    }
  }
  if (h(0, seed, 40) < (p.pipeChance || 0.0)) {
    const pipeY = y + size * 0.4 + h(0, seed, 41) * size * 0.2;
    ctx.fillStyle = shiftColor(pal.secondary, 15); ctx.fillRect(x, pipeY, size, 4);
    ctx.fillStyle = shiftColor(pal.secondary, 8); ctx.fillRect(x, pipeY + 1, size, 2);
  }
  ctx.fillStyle = pal.mortar;
  for (let r = 1; r < (p.brickRows || 2); r++) ctx.fillRect(x, y + r * pH, size, mw);
  for (let c = 1; c < (p.brickCols || 2); c++) ctx.fillRect(x + c * pW, y, mw, size);
  if (p.edgeVignette) _edgeVig(ctx, x, y, size);
}

function drawWall_roughHewn(ctx, x, y, size, seed, pal, p) {
  const h = cellHash, mw = p.mortarWidth || 2, bRows = p.brickRows || 3, bH = size / bRows;
  ctx.fillStyle = pal.primary; ctx.fillRect(x, y, size, size);
  for (let r = 0; r < bRows; r++) {
    const numBlocks = 2 + Math.floor(h(r, seed, 1) * 3);
    let cx = x;
    for (let c = 0; c < numBlocks; c++) {
      const fraction = (1 / numBlocks) + (h(r * 10 + c, seed, 2) - 0.5) * 0.3;
      const bW = Math.max(8, size * fraction);
      const dX = cx + mw, dY = y + r * bH + mw;
      const dW = Math.min(bW - mw * 2, x + size - mw - dX), dH = bH - mw * 2;
      if (dW <= 2 || dH <= 2 || dX >= x + size - mw) break;
      ctx.fillStyle = varyColor(pal.secondary, 10, h(r * 10 + c, seed, 3)); ctx.fillRect(dX, dY, dW, dH);
      ctx.fillStyle = shiftColor(pal.secondary, 8); ctx.fillRect(dX, dY, dW, 1);
      ctx.fillStyle = shiftColor(pal.primary, -5); ctx.fillRect(dX, dY + dH - 1, dW, 1);
      const chiselCount = 2 + Math.floor(h(r * 10 + c, seed, 4) * 2);
      ctx.strokeStyle = shiftColor(pal.secondary, -8); ctx.lineWidth = 0.8;
      for (let m = 0; m < chiselCount; m++) {
        const mx = dX + h(r * 10 + c + m, seed, 5) * (dW - 4) + 2, my = dY + h(r * 10 + c + m, seed, 6) * (dH - 4) + 2;
        ctx.beginPath(); ctx.moveTo(mx, my); ctx.lineTo(mx + 2 + h(m, seed, 7) * 2, my + 1 + h(m, seed, 8)); ctx.stroke();
      }
      cx += bW;
    }
  }
  ctx.fillStyle = pal.mortar;
  for (let r = 1; r < bRows; r++) ctx.fillRect(x, y + r * bH - 1, size, mw);
}

function drawWall_boneStack(ctx, x, y, size, seed, pal, p) {
  const h = cellHash, bRows = p.boneRows || 4, sw = p.seamWidth || 1, rowH = size / bRows;
  ctx.fillStyle = pal.primary; ctx.fillRect(x, y, size, size);
  for (let r = 0; r < bRows; r++) {
    const numBones = 3 + Math.floor(h(r, seed, 1) * 3);
    let cx = x;
    for (let b = 0; b < numBones; b++) {
      const bW = (size / numBones) + (h(r * 10 + b, seed, 2) - 0.5) * 6;
      const dX = cx + 1, dY = y + r * rowH + sw, dW = Math.min(bW - 2, x + size - 1 - dX), dH = rowH - sw * 2;
      if (dW <= 4 || dH <= 2 || dX >= x + size - 1) break;
      ctx.fillStyle = varyColor(pal.secondary, 4, h(r * 10 + b, seed, 3));
      const rad = Math.min(2, dW / 4, dH / 4);
      ctx.beginPath();
      ctx.moveTo(dX + rad, dY); ctx.lineTo(dX + dW - rad, dY);
      ctx.arcTo(dX + dW, dY, dX + dW, dY + rad, rad); ctx.lineTo(dX + dW, dY + dH - rad);
      ctx.arcTo(dX + dW, dY + dH, dX + dW - rad, dY + dH, rad); ctx.lineTo(dX + rad, dY + dH);
      ctx.arcTo(dX, dY + dH, dX, dY + dH - rad, rad); ctx.lineTo(dX, dY + rad);
      ctx.arcTo(dX, dY, dX + rad, dY, rad); ctx.closePath(); ctx.fill();
      ctx.fillStyle = shiftColor(pal.secondary, 6); ctx.fillRect(dX + rad, dY + 1, dW - rad * 2, 1);
      cx += bW;
    }
    if (r < bRows - 1) { ctx.fillStyle = pal.mortar; ctx.fillRect(x, y + (r + 1) * rowH - 1, size, sw); }
  }
}

function drawWall_ashlarBlock(ctx, x, y, size, seed, pal, p) {
  const h = cellHash, bRows = p.blockRows || 3, bCols = p.blockCols || 2, mw = p.mortarWidth || 1;
  const bH = size / bRows, bW = size / bCols;
  ctx.fillStyle = pal.primary; ctx.fillRect(x, y, size, size);
  for (let r = 0; r < bRows; r++) {
    for (let c = 0; c < bCols; c++) {
      const bx = x + c * bW + mw, by = y + r * bH + mw, bw = bW - mw * 2, bh = bH - mw * 2;
      if (bw <= 2 || bh <= 2) continue;
      ctx.fillStyle = varyColor(pal.secondary, 5, h(r * 10 + c, seed, 1)); ctx.fillRect(bx, by, bw, bh);
      ctx.fillStyle = shiftColor(pal.secondary, 6); ctx.fillRect(bx, by, bw, 1);
      ctx.fillStyle = shiftColor(pal.primary, -3); ctx.fillRect(bx, by + bh - 1, bw, 1);
      ctx.strokeStyle = shiftColor(pal.secondary, -4); ctx.lineWidth = 0.5; ctx.strokeRect(bx + 2, by + 2, bw - 4, bh - 4);
    }
  }
  ctx.fillStyle = pal.mortar;
  for (let r = 1; r < bRows; r++) ctx.fillRect(x, y + r * bH - 1, size, mw);
  for (let c = 1; c < bCols; c++) ctx.fillRect(x + c * bW - 1, y, mw, size);
}

function _edgeVig(ctx, x, y, s) {
  ctx.fillStyle = 'rgba(0,0,0,0.12)';
  ctx.fillRect(x, y, s, 2); ctx.fillRect(x, y + s - 2, s, 2);
  ctx.fillRect(x, y, 2, s); ctx.fillRect(x + s - 2, y, 2, s);
}

function _rivet(ctx, cx, cy, pal) {
  ctx.fillStyle = shiftColor(pal.secondary, 15); ctx.beginPath(); ctx.arc(cx, cy, 1.5, 0, Math.PI * 2); ctx.fill();
  ctx.fillStyle = shiftColor(pal.secondary, -5); ctx.beginPath(); ctx.arc(cx + 0.5, cy + 0.5, 0.8, 0, Math.PI * 2); ctx.fill();
}

function drawWall_fungalGrowth(ctx, x, y, size, seed, pal, p) {
  const h = cellHash;
  ctx.fillStyle = pal.primary; ctx.fillRect(x, y, size, size);
  const massCount = 4 + Math.floor(h(0, seed, 1) * 3);
  for (let i = 0; i < massCount; i++) {
    const cx = x + h(i, seed, 2) * size, cy = y + h(i, seed, 3) * size;
    const rx = size * 0.15 + h(i, seed, 4) * size * 0.2, ry = size * 0.12 + h(i, seed, 5) * size * 0.18;
    ctx.fillStyle = varyColor(pal.secondary, 6, h(i, seed, 6));
    ctx.beginPath(); ctx.ellipse(cx, cy, rx, ry, h(i, seed, 7) * Math.PI, 0, Math.PI * 2); ctx.fill();
  }
  const dotCount = 2 + Math.floor(h(0, seed, 10) * 2);
  for (let i = 0; i < dotCount; i++) {
    const dx = x + h(i, seed, 11) * (size - 6) + 3, dy = y + h(i, seed, 12) * (size - 6) + 3;
    const grad = ctx.createRadialGradient(dx, dy, 0, dx, dy, 4);
    grad.addColorStop(0, hexAlpha(pal.highlight, 0.6)); grad.addColorStop(1, hexAlpha(pal.highlight, 0));
    ctx.fillStyle = grad; ctx.fillRect(dx - 4, dy - 4, 8, 8);
    ctx.fillStyle = pal.accent; ctx.fillRect(dx, dy, 1, 1);
  }
  ctx.strokeStyle = hexAlpha(pal.accent, 0.25); ctx.lineWidth = 0.8;
  for (let i = 0; i < 2; i++) {
    const tx = x + h(i, seed, 20) * (size - 4) + 2;
    ctx.beginPath(); ctx.moveTo(tx, y);
    ctx.quadraticCurveTo(tx + (h(i, seed, 21) - 0.5) * 8, y + size * 0.3, tx + (h(i, seed, 22) - 0.5) * 6, y + size * 0.5); ctx.stroke();
    const bx = x + h(i + 2, seed, 20) * (size - 4) + 2;
    ctx.beginPath(); ctx.moveTo(bx, y + size);
    ctx.quadraticCurveTo(bx + (h(i + 2, seed, 21) - 0.5) * 8, y + size * 0.7, bx + (h(i + 2, seed, 22) - 0.5) * 6, y + size * 0.5); ctx.stroke();
  }
}

function drawWall_iceCrystal(ctx, x, y, size, seed, pal, p) {
  const h = cellHash;
  ctx.fillStyle = pal.primary; ctx.fillRect(x, y, size, size);
  const facetCount = 3 + Math.floor(h(0, seed, 1) * 2);
  const cx = x + size / 2, cy = y + size / 2;
  for (let i = 0; i < facetCount; i++) {
    const angle = (i / facetCount) * Math.PI * 2 + h(i, seed, 2) * 0.5;
    const nextAngle = ((i + 1) / facetCount) * Math.PI * 2 + h(i + 1, seed, 2) * 0.5;
    const r1 = size * 0.3 + h(i, seed, 3) * size * 0.2, r2 = size * 0.3 + h(i + 1, seed, 3) * size * 0.2;
    ctx.fillStyle = varyColor(pal.secondary, 8, h(i, seed, 4));
    ctx.beginPath(); ctx.moveTo(cx, cy);
    ctx.lineTo(cx + Math.cos(angle) * r1, cy + Math.sin(angle) * r1);
    ctx.lineTo(cx + Math.cos(nextAngle) * r2, cy + Math.sin(nextAngle) * r2); ctx.closePath(); ctx.fill();
    ctx.strokeStyle = hexAlpha('#ffffff', 0.15); ctx.lineWidth = 0.8; ctx.beginPath();
    ctx.moveTo(cx + Math.cos(angle) * r1, cy + Math.sin(angle) * r1);
    ctx.lineTo(cx + Math.cos(nextAngle) * r2, cy + Math.sin(nextAngle) * r2); ctx.stroke();
  }
  const hlFacet = Math.floor(h(0, seed, 10) * facetCount);
  const hlAngle = (hlFacet / facetCount) * Math.PI * 2 + h(hlFacet, seed, 2) * 0.5;
  const hlR = size * 0.15 + h(hlFacet, seed, 11) * size * 0.1;
  ctx.fillStyle = hexAlpha(pal.highlight, 0.2); ctx.beginPath();
  ctx.arc(cx + Math.cos(hlAngle) * hlR, cy + Math.sin(hlAngle) * hlR, size * 0.08, 0, Math.PI * 2); ctx.fill();
  ctx.fillStyle = hexAlpha(pal.primary, 0.3);
  ctx.fillRect(x, y, size, 2); ctx.fillRect(x, y + size - 2, size, 2);
  ctx.fillRect(x, y, 2, size); ctx.fillRect(x + size - 2, y, 2, size);
}

function drawWall_bloodStone(ctx, x, y, size, seed, pal, p) {
  const { blockRows = 2, blockCols = 2, mortarWidth = 2 } = p;
  const h = cellHash, bH = size / blockRows, bW = size / blockCols;
  ctx.fillStyle = pal.primary; ctx.fillRect(x, y, size, size);
  for (let r = 0; r < blockRows; r++) for (let c = 0; c < blockCols; c++) {
    const bx = x + c * bW + mortarWidth, by = y + r * bH + mortarWidth;
    const bw = bW - mortarWidth * 2, bh = bH - mortarWidth * 2;
    if (bw <= 2 || bh <= 2) continue;
    ctx.fillStyle = varyColor(pal.secondary, 5, h(r * 10 + c, seed, 1)); ctx.fillRect(bx, by, bw, bh);
    ctx.fillStyle = shiftColor(pal.secondary, 5); ctx.fillRect(bx, by, bw, 1);
    ctx.fillStyle = shiftColor(pal.primary, -3); ctx.fillRect(bx, by + bh - 1, bw, 1);
    const veinCount = 1 + Math.floor(h(r * 10 + c, seed, 5) * 2);
    ctx.strokeStyle = hexAlpha(pal.accent, 0.35); ctx.lineWidth = 0.8;
    for (let v = 0; v < veinCount; v++) {
      const vx1 = bx + h(r * 10 + c + v, seed, 6) * bw, vy1 = by + h(r * 10 + c + v, seed, 7) * bh;
      const vx2 = bx + h(r * 10 + c + v, seed, 8) * bw, vy2 = by + h(r * 10 + c + v, seed, 9) * bh;
      const cpx = bx + h(r * 10 + c + v, seed, 10) * bw, cpy = by + h(r * 10 + c + v, seed, 11) * bh;
      ctx.beginPath(); ctx.moveTo(vx1, vy1); ctx.quadraticCurveTo(cpx, cpy, vx2, vy2); ctx.stroke();
    }
  }
  if (h(0, seed, 20) < 0.35) {
    const sx = x + size * 0.3 + h(0, seed, 21) * size * 0.4, sy = y + size * 0.3 + h(0, seed, 22) * size * 0.4;
    ctx.strokeStyle = hexAlpha(pal.highlight, 0.25); ctx.lineWidth = 1; ctx.beginPath();
    ctx.moveTo(sx, sy - 3); ctx.lineTo(sx + 3, sy); ctx.lineTo(sx, sy + 3); ctx.lineTo(sx - 3, sy); ctx.closePath(); ctx.stroke();
  }
  ctx.fillStyle = pal.mortar;
  for (let r = 1; r < blockRows; r++) ctx.fillRect(x, y + r * bH - 1, size, mortarWidth);
  for (let c = 1; c < blockCols; c++) ctx.fillRect(x + c * bW - 1, y, mortarWidth, size);
  ctx.fillStyle = hexAlpha(pal.accent, 0.08);
  for (let r = 1; r < blockRows; r++) ctx.fillRect(x, y + r * bH - 2, size, mortarWidth + 2);
  for (let c = 1; c < blockCols; c++) ctx.fillRect(x + c * bW - 2, y, mortarWidth + 2, size);
}

// ═══════════════════════════════════════════════════════════
//  FLOOR DRAWING FUNCTIONS
// ═══════════════════════════════════════════════════════════

function drawFloor_flagstone(ctx, x, y, size, seed, pal, p) {
  const h = cellHash, sg = p.slabGrid || 2, gw = p.groutWidth || 1, sW = size / sg;
  const texDots = p.textureDots != null ? p.textureDots : 1;
  ctx.fillStyle = pal.floor; ctx.fillRect(x, y, size, size);
  for (let r = 0; r < sg; r++) for (let c = 0; c < sg; c++) {
    const v = h(r * 3 + c, seed, 100);
    ctx.fillStyle = varyColor(pal.floor, 3, v);
    ctx.fillRect(x + c * sW + gw, y + r * sW + gw, sW - gw * 2, sW - gw * 2);
    for (let d = 0; d < texDots; d++) {
      ctx.fillStyle = shiftColor(pal.floor, h(d, seed, 107) < 0.5 ? 3 : -3);
      ctx.fillRect(x + c * sW + gw + h(r * 3 + c + d, seed, 105) * (sW - gw * 2), y + r * sW + gw + h(r * 3 + c + d, seed, 106) * (sW - gw * 2), 1, 1);
    }
  }
  if (h(0, seed, 110) < (p.stainChance || 0.0)) {
    ctx.fillStyle = p.stainColor || 'rgba(120,20,20,0.35)';
    ctx.beginPath(); ctx.arc(x + h(0, seed, 111) * (size - 10) + 7, y + h(0, seed, 112) * (size - 10) + 7, 3 + h(0, seed, 113) * 4, 0, Math.PI * 2); ctx.fill();
  }
  if (h(0, seed, 120) < (p.debrisChance || 0.0)) {
    ctx.fillStyle = p.debrisColor || '#4a4040';
    ctx.fillRect(x + h(0, seed, 121) * (size - 6) + 2, y + h(0, seed, 122) * (size - 6) + 2, 2, 1);
  }
}

function drawFloor_ashCovered(ctx, x, y, size, seed, pal, p) {
  const h = cellHash, sg = p.slabGrid || 2, gw = p.groutWidth || 1, sW = size / sg;
  ctx.fillStyle = pal.floor; ctx.fillRect(x, y, size, size);
  for (let r = 0; r < sg; r++) for (let c = 0; c < sg; c++) {
    ctx.fillStyle = varyColor(pal.floor, 3, h(r * 3 + c, seed, 100));
    ctx.fillRect(x + c * sW + gw, y + r * sW + gw, sW - gw * 2, sW - gw * 2);
  }
  const ac = Math.floor((p.ashDensity || 0.08) * 20);
  for (let i = 0; i < ac; i++) {
    ctx.fillStyle = `rgba(60,55,50,${0.2 + h(i, seed, 133) * 0.3})`;
    ctx.fillRect(x + h(i, seed, 130) * size, y + h(i, seed, 131) * size, 1 + h(i, seed, 132) * 2, 1 + h(i, seed, 132) * 1);
  }
  if (h(0, seed, 140) < (p.emberChance || 0.0)) {
    const ex = x + h(0, seed, 141) * (size - 4) + 2, ey = y + h(0, seed, 142) * (size - 4) + 2;
    ctx.fillStyle = hexAlpha(pal.highlight, 0.5); ctx.fillRect(ex, ey, 2, 2);
    ctx.fillStyle = hexAlpha(pal.accent, 0.15); ctx.beginPath(); ctx.arc(ex + 1, ey + 1, 3, 0, Math.PI * 2); ctx.fill();
  }
}

function drawFloor_flooded(ctx, x, y, size, seed, pal, p) {
  const h = cellHash, sg = p.slabGrid || 2, gw = p.groutWidth || 1, sW = size / sg;
  ctx.fillStyle = pal.floor; ctx.fillRect(x, y, size, size);
  for (let r = 0; r < sg; r++) for (let c = 0; c < sg; c++) {
    ctx.fillStyle = varyColor(pal.floor, 3, h(r * 3 + c, seed, 100));
    ctx.fillRect(x + c * sW + gw, y + r * sW + gw, sW - gw * 2, sW - gw * 2);
  }
  ctx.fillStyle = `rgba(10,30,50,${p.waterDepth || 0.08})`; ctx.fillRect(x, y, size, size);
  if (h(0, seed, 150) < (p.rippleChance || 0.0)) {
    const rx = x + size * 0.3 + h(0, seed, 151) * size * 0.4, ry = y + size * 0.3 + h(0, seed, 152) * size * 0.4;
    ctx.strokeStyle = hexAlpha(pal.accent, 0.10); ctx.lineWidth = 0.5;
    ctx.beginPath(); ctx.arc(rx, ry, 4 + h(0, seed, 153) * 5, 0, Math.PI * 2); ctx.stroke();
  }
}

function drawFloor_crackedMarble(ctx, x, y, size, seed, pal, p) {
  const h = cellHash, sg = p.slabGrid || 3, gw = p.groutWidth || 1, sW = size / sg;
  ctx.fillStyle = pal.floor; ctx.fillRect(x, y, size, size);
  for (let r = 0; r < sg; r++) for (let c = 0; c < sg; c++) {
    ctx.fillStyle = varyColor(pal.floor, 3, h(r * 3 + c, seed, 100));
    ctx.fillRect(x + c * sW + gw, y + r * sW + gw, sW - gw * 2, sW - gw * 2);
    if (h(r * 3 + c, seed, 105) < (p.veinChance || 0.0)) {
      ctx.strokeStyle = shiftColor(pal.floor, 6); ctx.lineWidth = 0.5; ctx.beginPath();
      ctx.moveTo(x + c * sW + gw + h(r + c, seed, 106) * (sW - gw * 2), y + r * sW + gw);
      ctx.lineTo(x + c * sW + sW - gw - h(r + c, seed, 107) * (sW - gw * 2) * 0.5, y + r * sW + sW - gw);
      ctx.stroke();
    }
  }
  if (h(0, seed, 170) < (p.crackChance || 0.0)) {
    ctx.strokeStyle = shiftColor(pal.grout, 5); ctx.lineWidth = 0.8; ctx.beginPath();
    ctx.moveTo(x + h(0, seed, 171) * size, y); ctx.lineTo(x + h(0, seed, 172) * size, y + size); ctx.stroke();
  }
  if (h(0, seed, 190) < (p.debrisChance || 0.0)) {
    ctx.fillStyle = p.debrisColor || '#3a3045';
    ctx.fillRect(x + h(0, seed, 191) * (size - 6) + 2, y + h(0, seed, 192) * (size - 6) + 2, 3, 2);
  }
}

function drawFloor_metalGrate(ctx, x, y, size, seed, pal, p) {
  const h = cellHash, sp = p.grateLineSpacing || 6;
  ctx.fillStyle = pal.floor; ctx.fillRect(x, y, size, size);
  ctx.strokeStyle = shiftColor(pal.floor, -10); ctx.lineWidth = 1;
  for (let i = sp; i < size; i += sp) {
    ctx.beginPath(); ctx.moveTo(x, y + i); ctx.lineTo(x + size, y + i); ctx.stroke();
  }
  for (let i = sp; i < size; i += sp) {
    ctx.beginPath(); ctx.moveTo(x + i, y); ctx.lineTo(x + i, y + size); ctx.stroke();
  }
  ctx.strokeStyle = shiftColor(pal.floor, 5); ctx.lineWidth = 0.5;
  for (let i = sp; i < size; i += sp) { ctx.beginPath(); ctx.moveTo(x, y + i - 1); ctx.lineTo(x + size, y + i - 1); ctx.stroke(); }
  ctx.strokeStyle = hexAlpha(pal.secondary, 0.15); ctx.lineWidth = 0.5; ctx.strokeRect(x + 0.5, y + 0.5, size - 1, size - 1);
  if (h(0, seed, 200) < (p.oilChance || 0.0)) {
    ctx.fillStyle = p.stainColor || 'rgba(90,60,30,0.30)'; ctx.beginPath();
    ctx.ellipse(x + h(0, seed, 201) * (size - 10) + 8, y + h(0, seed, 202) * (size - 10) + 7, 4 + h(0, seed, 203) * 3, 2 + h(0, seed, 204) * 2, 0, 0, Math.PI * 2);
    ctx.fill();
  }
}

function drawFloor_packedEarth(ctx, x, y, size, seed, pal, p) {
  const h = cellHash;
  ctx.fillStyle = pal.floor; ctx.fillRect(x, y, size, size);
  const pebbleCount = 4 + Math.floor(h(0, seed, 100) * 5);
  for (let i = 0; i < pebbleCount; i++) {
    const px = x + h(i, seed, 101) * (size - 4) + 2, py = y + h(i, seed, 102) * (size - 4) + 2;
    const pSize = 1 + Math.floor(h(i, seed, 103) * 2);
    ctx.fillStyle = shiftColor(pal.floor, h(i, seed, 104) < 0.5 ? 5 : -5);
    ctx.beginPath(); ctx.arc(px, py, pSize * 0.5, 0, Math.PI * 2); ctx.fill();
  }
  const scratchCount = 1 + Math.floor(h(0, seed, 110) * 2);
  ctx.strokeStyle = shiftColor(pal.floor, -3); ctx.lineWidth = 0.5;
  for (let i = 0; i < scratchCount; i++) {
    const sx = x + h(i, seed, 111) * size, sy = y + h(i, seed, 112) * size * 0.3;
    ctx.beginPath(); ctx.moveTo(sx, sy);
    ctx.lineTo(sx + h(i, seed, 113) * size * 0.4, sy + size * 0.6 + h(i, seed, 114) * size * 0.3); ctx.stroke();
  }
}

function drawFloor_polishedSlab(ctx, x, y, size, seed, pal, p) {
  const h = cellHash, sg = p.slabGrid || 2, gw = p.groutWidth || 1, sW = size / sg;
  ctx.fillStyle = pal.floor; ctx.fillRect(x, y, size, size);
  for (let r = 0; r < sg; r++) for (let c = 0; c < sg; c++) {
    ctx.fillStyle = varyColor(pal.floor, 1, h(r * 3 + c, seed, 100));
    ctx.fillRect(x + c * sW + gw, y + r * sW + gw, sW - gw * 2, sW - gw * 2);
    if (h(r * 3 + c, seed, 105) < 0.4) {
      ctx.fillStyle = shiftColor(pal.floor, 3);
      ctx.fillRect(x + c * sW + gw + 2, y + r * sW + gw + (sW - gw * 2) * 0.3, sW - gw * 2 - 4, 1);
    }
  }
  ctx.fillStyle = hexAlpha(pal.grout, 0.08);
  for (let r = 1; r < sg; r++) ctx.fillRect(x, y + r * sW, size, 1);
  for (let c = 1; c < sg; c++) ctx.fillRect(x + c * sW, y, 1, size);
}

function drawFloor_dustyTile(ctx, x, y, size, seed, pal, p) {
  const h = cellHash, sg = p.slabGrid || 3, gw = p.groutWidth || 1, sW = size / sg;
  ctx.fillStyle = pal.floor; ctx.fillRect(x, y, size, size);
  for (let r = 0; r < sg; r++) for (let c = 0; c < sg; c++) {
    ctx.fillStyle = varyColor(pal.floor, 3, h(r * 3 + c, seed, 100));
    ctx.fillRect(x + c * sW + gw, y + r * sW + gw, sW - gw * 2, sW - gw * 2);
    const dx = x + c * sW + gw + h(r * 3 + c, seed, 105) * (sW - gw * 2 - 2) + 1;
    const dy = y + r * sW + gw + h(r * 3 + c, seed, 106) * (sW - gw * 2 - 2) + 1;
    ctx.fillStyle = shiftColor(pal.floor, 4); ctx.fillRect(dx, dy, 1, 1);
  }
  ctx.fillStyle = 'rgba(40,40,50,0.04)'; ctx.fillRect(x, y, size, size);
}

function drawFloor_myceliumMat(ctx, x, y, size, seed, pal, p) {
  const h = cellHash;
  ctx.fillStyle = pal.floor; ctx.fillRect(x, y, size, size);
  ctx.fillStyle = varyColor(pal.floor, 3, h(0, seed, 100)); ctx.fillRect(x + 2, y + 2, size - 4, size - 4);
  const lineCount = 2 + Math.floor(h(0, seed, 1) * 2);
  ctx.strokeStyle = hexAlpha(pal.accent, 0.2); ctx.lineWidth = 0.6;
  for (let i = 0; i < lineCount; i++) {
    const sx = x + h(i, seed, 2) * size, sy = y + h(i, seed, 3) * size;
    const ex = x + h(i, seed, 4) * size, ey = y + h(i, seed, 5) * size;
    const cpx = x + h(i, seed, 6) * size, cpy = y + h(i, seed, 7) * size;
    ctx.beginPath(); ctx.moveTo(sx, sy); ctx.quadraticCurveTo(cpx, cpy, ex, ey); ctx.stroke();
    if (h(i, seed, 8) > 0.4) {
      const fx = (ex + cpx) / 2 + (h(i, seed, 9) - 0.5) * size * 0.3;
      const fy = (ey + cpy) / 2 + (h(i, seed, 10) - 0.5) * size * 0.3;
      ctx.beginPath(); ctx.moveTo((sx + cpx) / 2, (sy + cpy) / 2); ctx.lineTo(fx, fy); ctx.stroke();
    }
  }
  const sporeCount = 3 + Math.floor(h(0, seed, 20) * 3);
  ctx.fillStyle = hexAlpha(pal.highlight, 0.2);
  for (let i = 0; i < sporeCount; i++) {
    ctx.fillRect(x + h(i, seed, 21) * (size - 2) + 1, y + h(i, seed, 22) * (size - 2) + 1, 1, 1);
  }
}

function drawFloor_frozenStone(ctx, x, y, size, seed, pal, p) {
  const { slabGrid: sg = 2, groutWidth: gw = 1 } = p, h = cellHash, sW = size / sg;
  ctx.fillStyle = pal.floor; ctx.fillRect(x, y, size, size);
  for (let r = 0; r < sg; r++) for (let c = 0; c < sg; c++) {
    ctx.fillStyle = varyColor(pal.floor, 3, h(r * 3 + c, seed, 100));
    ctx.fillRect(x + c * sW + gw, y + r * sW + gw, sW - gw * 2, sW - gw * 2);
  }
  ctx.fillStyle = 'rgba(200,220,255,0.04)'; ctx.fillRect(x, y, size, size);
  const glintCount = 1 + Math.floor(h(0, seed, 1) * 2);
  for (let i = 0; i < glintCount; i++) {
    ctx.fillStyle = hexAlpha(pal.highlight, 0.4);
    ctx.fillRect(x + h(i, seed, 2) * (size - 4) + 2, y + h(i, seed, 3) * (size - 4) + 2, 1, 1);
  }
  if (h(0, seed, 10) < 0.35) {
    ctx.strokeStyle = hexAlpha(pal.highlight, 0.15); ctx.lineWidth = 0.8;
    ctx.beginPath(); ctx.moveTo(x + h(0, seed, 11) * size, y + h(0, seed, 12) * size);
    ctx.lineTo(x + h(0, seed, 13) * size, y + h(0, seed, 14) * size); ctx.stroke();
  }
}

function drawFloor_ritualTile(ctx, x, y, size, seed, pal, p) {
  const { slabGrid: sg = 3, groutWidth: gw = 1 } = p, h = cellHash, sW = size / sg;
  ctx.fillStyle = pal.floor; ctx.fillRect(x, y, size, size);
  ctx.fillStyle = hexAlpha(pal.accent, 0.04); ctx.fillRect(x, y, size, size);
  for (let r = 0; r < sg; r++) for (let c = 0; c < sg; c++) {
    const sx = x + c * sW, sy = y + r * sW;
    ctx.fillStyle = varyColor(pal.floor, 3, h(r * sg + c, seed, 100));
    ctx.fillRect(sx + gw, sy + gw, sW - gw * 2, sW - gw * 2);
    ctx.strokeStyle = hexAlpha(pal.accent, 0.12); ctx.lineWidth = 0.5; ctx.beginPath();
    if ((r + c) % 2 === 0) { ctx.moveTo(sx, sy + sW); ctx.lineTo(sx + sW, sy); }
    else { ctx.moveTo(sx, sy); ctx.lineTo(sx + sW, sy + sW); }
    ctx.stroke();
    if (h(r * sg + c, seed, 1) < 0.3) {
      ctx.fillStyle = hexAlpha(pal.highlight, 0.35); ctx.fillRect(sx + sW / 2, sy + sW / 2, 1, 1);
    }
  }
  ctx.strokeStyle = hexAlpha(pal.accent, 0.15); ctx.lineWidth = 0.5;
  for (let r = 1; r < sg; r++) { ctx.beginPath(); ctx.moveTo(x, y + r * sW); ctx.lineTo(x + size, y + r * sW); ctx.stroke(); }
  for (let c = 1; c < sg; c++) { ctx.beginPath(); ctx.moveTo(x + c * sW, y); ctx.lineTo(x + c * sW, y + size); ctx.stroke(); }
}

// ═══════════════════════════════════════════════════════════
//  CORRIDOR + SPECIAL TILES
// ═══════════════════════════════════════════════════════════

function drawCorridor(ctx, x, y, size, seed, pal, theme) {
  const cs = theme.corridor?.style || 'worn_stone', h = cellHash, sW = size / 2;
  ctx.fillStyle = shiftColor(pal.floor, -3); ctx.fillRect(x, y, size, size);
  for (let r = 0; r < 2; r++) for (let c = 0; c < 2; c++) {
    ctx.fillStyle = varyColor(pal.floor, 3, h(r * 3 + c, seed, 200));
    ctx.fillRect(x + c * sW + 1, y + r * sW + 1, sW - 2, sW - 2);
  }
  switch (cs) {
    case 'worn_stone':
      if (h(0, seed, 210) < (theme.corridor.streakChance || 0.0)) {
        ctx.fillStyle = hexAlpha(pal.accent, 0.2); ctx.fillRect(x + size * 0.3 + h(0, seed, 211) * size * 0.3, y, 2, size);
      } break;
    case 'ash_trail': {
      const ac2 = Math.floor((theme.corridor.ashDensity || 0.15) * 25);
      for (let i = 0; i < ac2; i++) { ctx.fillStyle = `rgba(60,55,50,${0.15 + h(i, seed, 222) * 0.25})`; ctx.fillRect(x + h(i, seed, 220) * size, y + h(i, seed, 221) * size, 1 + h(i, seed, 223), 1); }
    } break;
    case 'shallow_water':
      ctx.fillStyle = `rgba(10,30,50,${theme.corridor.waterDepth || 0.15})`; ctx.fillRect(x, y, size, size); break;
    case 'worn_carpet': {
      const cW = size * 0.4; ctx.fillStyle = theme.corridor.carpetColor || 'rgba(80,40,50,0.20)';
      ctx.fillRect(x + (size - cW) / 2, y, cW, size);
      ctx.fillStyle = shiftColor(pal.floor, 3);
      ctx.fillRect(x + (size - cW) / 2 - 1, y, 1, size); ctx.fillRect(x + (size + cW) / 2, y, 1, size);
    } break;
    case 'walkway':
      if (theme.corridor.railHint) {
        ctx.fillStyle = shiftColor(pal.secondary, 8); ctx.fillRect(x, y, 2, size); ctx.fillRect(x + size - 2, y, 2, size);
        ctx.fillStyle = shiftColor(pal.secondary, 3); ctx.fillRect(x + 2, y, 1, size); ctx.fillRect(x + size - 3, y, 1, size);
      } break;
  }
}

function drawSpawn(ctx, x, y, size, seed, pal, theme) {
  drawCorridor(ctx, x, y, size, seed, pal, theme);
  ctx.strokeStyle = hexAlpha(pal.accent, 0.15); ctx.lineWidth = 1;
  ctx.beginPath(); ctx.arc(x + size / 2, y + size / 2, size * 0.3, 0, Math.PI * 2); ctx.stroke();
}

// ═══════════════════════════════════════════════════════════
//  WALL-EDGE TRANSITION FUNCTIONS
// ═══════════════════════════════════════════════════════════

function drawEdge_crumble(ctx, x, y, size, side, seed, pal, ec) {
  const h = cellHash, w = ec.width || 4, alpha = ec.intensity || 0.6;
  const count = 2 + Math.floor(h(seed, 0, 60) * 2);
  for (let i = 0; i < count; i++) {
    const pos = h(seed, i, 61) * (size - 6) + 2, rw = 3 + h(seed, i, 62) * 4, rh = 2 + h(seed, i, 63) * (w - 1);
    ctx.fillStyle = hexAlpha(pal.secondary, alpha);
    if (side === 'top') ctx.fillRect(x + pos, y, rw, rh);
    else if (side === 'bottom') ctx.fillRect(x + pos, y + size - rh, rw, rh);
    else if (side === 'left') ctx.fillRect(x, y + pos, rh, rw);
    else ctx.fillRect(x + size - rh, y + pos, rh, rw);
  }
}

function drawEdge_scorch(ctx, x, y, size, side, seed, pal, ec) {
  const w = ec.width || 4, alpha = ec.intensity || 0.7;
  for (let i = 0; i < w; i++) {
    const a = alpha * (1 - i / w) * 0.3;
    ctx.fillStyle = `rgba(10, 8, 5, ${a})`;
    if (side === 'top') ctx.fillRect(x, y + i, size, 1);
    else if (side === 'bottom') ctx.fillRect(x, y + size - 1 - i, size, 1);
    else if (side === 'left') ctx.fillRect(x + i, y, 1, size);
    else ctx.fillRect(x + size - 1 - i, y, 1, size);
  }
}

function drawEdge_mossCreep(ctx, x, y, size, side, seed, pal, ec) {
  const h = cellHash, w = ec.width || 3, alpha = ec.intensity || 0.5;
  ctx.strokeStyle = hexAlpha(pal.accent, alpha * 0.5); ctx.lineWidth = 1; ctx.beginPath();
  const segs = 4 + Math.floor(h(seed, 0, 70) * 3);
  if (side === 'top' || side === 'bottom') {
    const ey = side === 'top' ? y + 1 : y + size - 2; ctx.moveTo(x, ey);
    for (let i = 1; i <= segs; i++) ctx.lineTo(x + (i / segs) * size, ey + (h(seed, i, 71) - 0.5) * w);
  } else {
    const ex = side === 'left' ? x + 1 : x + size - 2; ctx.moveTo(ex, y);
    for (let i = 1; i <= segs; i++) ctx.lineTo(ex + (h(seed, i, 72) - 0.5) * w, y + (i / segs) * size);
  }
  ctx.stroke();
  const dc = 2 + Math.floor(h(seed, 0, 73) * 2);
  ctx.fillStyle = hexAlpha(pal.accent, alpha * 0.3);
  for (let i = 0; i < dc; i++) {
    const pos = h(seed, i, 74) * (size - 4) + 2, off = h(seed, i, 75) * (w - 1);
    if (side === 'top') ctx.fillRect(x + pos, y + off, 2, 2);
    else if (side === 'bottom') ctx.fillRect(x + pos, y + size - 1 - off, 2, 2);
    else if (side === 'left') ctx.fillRect(x + off, y + pos, 2, 2);
    else ctx.fillRect(x + size - 1 - off, y + pos, 2, 2);
  }
}

function drawEdge_rubbleStrip(ctx, x, y, size, side, seed, pal, ec) {
  const h = cellHash, w = ec.width || 4, alpha = ec.intensity || 0.5;
  const dc = 5 + Math.floor(h(seed, 0, 80) * 4);
  for (let i = 0; i < dc; i++) {
    const pos = h(seed, i, 81) * (size - 2) + 1, off = h(seed, i, 82) * w, ds = 1 + Math.floor(h(seed, i, 83) * 1.5);
    ctx.fillStyle = hexAlpha(pal.secondary, alpha * (0.4 + h(seed, i, 84) * 0.3));
    if (side === 'top') ctx.fillRect(x + pos, y + off, ds, ds);
    else if (side === 'bottom') ctx.fillRect(x + pos, y + size - off - ds, ds, ds);
    else if (side === 'left') ctx.fillRect(x + off, y + pos, ds, ds);
    else ctx.fillRect(x + size - off - ds, y + pos, ds, ds);
  }
}

function drawEdge_rustDrip(ctx, x, y, size, side, seed, pal, ec) {
  const h = cellHash, w = ec.width || 3, alpha = ec.intensity || 0.6;
  const lines = 1 + Math.floor(h(seed, 0, 90) * 1.5);
  for (let l = 0; l < lines; l++) {
    const pos = 4 + h(seed, l, 91) * (size - 8);
    ctx.strokeStyle = hexAlpha(pal.accent, alpha * 0.4); ctx.lineWidth = 0.8; ctx.beginPath();
    const drift = (h(seed, l, 92) - 0.5) * 3;
    if (side === 'top') { ctx.moveTo(x + pos, y); ctx.lineTo(x + pos + drift, y + w); }
    else if (side === 'bottom') { ctx.moveTo(x + pos, y + size); ctx.lineTo(x + pos + drift, y + size - w); }
    else if (side === 'left') { ctx.moveTo(x, y + pos); ctx.lineTo(x + w, y + pos + drift); }
    else { ctx.moveTo(x + size, y + pos); ctx.lineTo(x + size - w, y + pos + drift); }
    ctx.stroke();
  }
}

function drawEdge_dustDrift(ctx, x, y, size, side, seed, pal, ec) {
  const w = ec.width || 2, alpha = ec.intensity || 0.4;
  for (let i = 0; i < w; i++) {
    const a = alpha * (1 - i / w) * 0.15;
    ctx.fillStyle = `rgba(60, 55, 45, ${a})`;
    if (side === 'top') ctx.fillRect(x, y + i, size, 1);
    else if (side === 'bottom') ctx.fillRect(x, y + size - 1 - i, size, 1);
    else if (side === 'left') ctx.fillRect(x + i, y, 1, size);
    else ctx.fillRect(x + size - 1 - i, y, 1, size);
  }
}

function drawEdge_cleanEdge(ctx, x, y, size, side, seed, pal, ec) {
  const alpha = ec.intensity || 0.3;
  ctx.fillStyle = hexAlpha(pal.grout, alpha);
  if (side === 'top') ctx.fillRect(x, y, size, 1);
  else if (side === 'bottom') ctx.fillRect(x, y + size - 1, size, 1);
  else if (side === 'left') ctx.fillRect(x, y, 1, size);
  else ctx.fillRect(x + size - 1, y, 1, size);
}

function drawEdge_seamLine(ctx, x, y, size, side, seed, pal, ec) {
  const alpha = ec.intensity || 0.4, inset = 2;
  ctx.strokeStyle = hexAlpha(pal.mortar, alpha); ctx.lineWidth = 1; ctx.beginPath();
  if (side === 'top') { ctx.moveTo(x + inset, y + inset); ctx.lineTo(x + size - inset, y + inset); }
  else if (side === 'bottom') { ctx.moveTo(x + inset, y + size - inset); ctx.lineTo(x + size - inset, y + size - inset); }
  else if (side === 'left') { ctx.moveTo(x + inset, y + inset); ctx.lineTo(x + inset, y + size - inset); }
  else { ctx.moveTo(x + size - inset, y + inset); ctx.lineTo(x + size - inset, y + size - inset); }
  ctx.stroke();
}

function drawEdge_sporeCreep(ctx, x, y, size, side, seed, pal, ec) {
  const h = cellHash, w = ec.width || 5, alpha = ec.intensity || 0.7;
  const tendrilCount = 2 + Math.floor(h(seed, 0, 80) * 2);
  ctx.strokeStyle = hexAlpha(pal.accent, alpha * 0.35); ctx.lineWidth = 0.7;
  for (let i = 0; i < tendrilCount; i++) {
    const pos = h(seed, i, 81) * (size - 6) + 3; ctx.beginPath();
    if (side === 'top') { ctx.moveTo(x + pos, y); ctx.quadraticCurveTo(x + pos + (h(seed, i, 82) - 0.5) * 4, y + w * 0.5, x + pos + (h(seed, i, 83) - 0.5) * 6, y + w); }
    else if (side === 'bottom') { ctx.moveTo(x + pos, y + size); ctx.quadraticCurveTo(x + pos + (h(seed, i, 82) - 0.5) * 4, y + size - w * 0.5, x + pos + (h(seed, i, 83) - 0.5) * 6, y + size - w); }
    else if (side === 'left') { ctx.moveTo(x, y + pos); ctx.quadraticCurveTo(x + w * 0.5, y + pos + (h(seed, i, 82) - 0.5) * 4, x + w, y + pos + (h(seed, i, 83) - 0.5) * 6); }
    else { ctx.moveTo(x + size, y + pos); ctx.quadraticCurveTo(x + size - w * 0.5, y + pos + (h(seed, i, 82) - 0.5) * 4, x + size - w, y + pos + (h(seed, i, 83) - 0.5) * 6); }
    ctx.stroke();
  }
  const dotCount = 3 + Math.floor(h(seed, 0, 85) * 2);
  ctx.fillStyle = hexAlpha(pal.highlight, alpha * 0.3);
  for (let i = 0; i < dotCount; i++) {
    const pos = h(seed, i, 86) * (size - 4) + 2, off = h(seed, i, 87) * (w - 1);
    if (side === 'top') ctx.fillRect(x + pos, y + off, 1, 1);
    else if (side === 'bottom') ctx.fillRect(x + pos, y + size - 1 - off, 1, 1);
    else if (side === 'left') ctx.fillRect(x + off, y + pos, 1, 1);
    else ctx.fillRect(x + size - 1 - off, y + pos, 1, 1);
  }
}

function drawEdge_frostCreep(ctx, x, y, size, side, seed, pal, ec) {
  const h = cellHash, w = ec.width || 6, alpha = ec.intensity || 0.8;
  for (let i = 0; i < w; i++) {
    const a = alpha * 0.08 * (1 - i / w); ctx.fillStyle = `rgba(200,220,255,${a})`;
    if (side === 'top') ctx.fillRect(x, y + i, size, 1);
    else if (side === 'bottom') ctx.fillRect(x, y + size - 1 - i, size, 1);
    else if (side === 'left') ctx.fillRect(x + i, y, 1, size);
    else ctx.fillRect(x + size - 1 - i, y, 1, size);
  }
  const crystalCount = 2 + Math.floor(h(seed, 0, 90) * 3);
  for (let i = 0; i < crystalCount; i++) {
    const pos = h(seed, i, 91) * (size - 4) + 2, off = h(seed, i, 92) * (w * 0.6);
    ctx.fillStyle = hexAlpha(pal.highlight, alpha * 0.4);
    if (side === 'top') ctx.fillRect(x + pos, y + off, 1, 1);
    else if (side === 'bottom') ctx.fillRect(x + pos, y + size - 1 - off, 1, 1);
    else if (side === 'left') ctx.fillRect(x + off, y + pos, 1, 1);
    else ctx.fillRect(x + size - 1 - off, y + pos, 1, 1);
  }
  ctx.strokeStyle = hexAlpha('#ffffff', alpha * 0.12); ctx.lineWidth = 0.5; ctx.beginPath();
  if (side === 'top') { ctx.moveTo(x, y + 1); ctx.lineTo(x + size, y + 1); }
  else if (side === 'bottom') { ctx.moveTo(x, y + size - 2); ctx.lineTo(x + size, y + size - 2); }
  else if (side === 'left') { ctx.moveTo(x + 1, y); ctx.lineTo(x + 1, y + size); }
  else { ctx.moveTo(x + size - 2, y); ctx.lineTo(x + size - 2, y + size); }
  ctx.stroke();
}

function drawEdge_bloodSeep(ctx, x, y, size, side, seed, pal, ec) {
  const h = cellHash, w = ec.width || 4, alpha = ec.intensity || 0.6;
  for (let i = 0; i < w; i++) {
    const a = alpha * 0.06 * (1 - i / w); ctx.fillStyle = hexAlpha(pal.accent, a);
    if (side === 'top') ctx.fillRect(x, y + i, size, 1);
    else if (side === 'bottom') ctx.fillRect(x, y + size - 1 - i, size, 1);
    else if (side === 'left') ctx.fillRect(x + i, y, 1, size);
    else ctx.fillRect(x + size - 1 - i, y, 1, size);
  }
  const dripCount = 1 + Math.floor(h(seed, 0, 95) * 2);
  ctx.strokeStyle = hexAlpha(pal.accent, alpha * 0.3); ctx.lineWidth = 0.6;
  for (let i = 0; i < dripCount; i++) {
    const pos = h(seed, i, 96) * (size - 6) + 3, len = w + h(seed, i, 97) * w * 0.5;
    ctx.beginPath();
    if (side === 'top') { ctx.moveTo(x + pos, y); ctx.lineTo(x + pos + (h(seed, i, 98) - 0.5) * 2, y + len); }
    else if (side === 'bottom') { ctx.moveTo(x + pos, y + size); ctx.lineTo(x + pos + (h(seed, i, 98) - 0.5) * 2, y + size - len); }
    else if (side === 'left') { ctx.moveTo(x, y + pos); ctx.lineTo(x + len, y + pos + (h(seed, i, 98) - 0.5) * 2); }
    else { ctx.moveTo(x + size, y + pos); ctx.lineTo(x + size - len, y + pos + (h(seed, i, 98) - 0.5) * 2); }
    ctx.stroke();
  }
}

// ═══════════════════════════════════════════════════════════
//  DISPATCH MAPS
// ═══════════════════════════════════════════════════════════

const WALL_FN = { cracked_stone: drawWall_crackedStone, scorched_brick: drawWall_scorchedBrick, mossy_stone: drawWall_mossyStone, carved_stone: drawWall_carvedStone, iron_plate: drawWall_ironPlate, rough_hewn: drawWall_roughHewn, bone_stack: drawWall_boneStack, ashlar_block: drawWall_ashlarBlock, fungal_growth: drawWall_fungalGrowth, ice_crystal: drawWall_iceCrystal, blood_stone: drawWall_bloodStone };
const FLOOR_FN = { flagstone: drawFloor_flagstone, ash_covered: drawFloor_ashCovered, flooded: drawFloor_flooded, cracked_marble: drawFloor_crackedMarble, metal_grate: drawFloor_metalGrate, packed_earth: drawFloor_packedEarth, polished_slab: drawFloor_polishedSlab, dusty_tile: drawFloor_dustyTile, mycelium_mat: drawFloor_myceliumMat, frozen_stone: drawFloor_frozenStone, ritual_tile: drawFloor_ritualTile };
const EDGE_FN = { crumble: drawEdge_crumble, scorch: drawEdge_scorch, moss_creep: drawEdge_mossCreep, rubble_strip: drawEdge_rubbleStrip, rust_drip: drawEdge_rustDrip, dust_drift: drawEdge_dustDrift, clean_edge: drawEdge_cleanEdge, seam_line: drawEdge_seamLine, spore_creep: drawEdge_sporeCreep, frost_creep: drawEdge_frostCreep, blood_seep: drawEdge_bloodSeep };

// ═══════════════════════════════════════════════════════════
//  THEME ENGINE CLASS
// ═══════════════════════════════════════════════════════════

const VARIANTS = 8;

export class ThemeEngine {
  constructor() {
    this.theme = null;
    this.tileSize = 48;
    this.cache = new Map();
    this._ready = false;

    // P-B: Offscreen fog canvas cache
    this._fogCanvas = null;
    this._fogCacheKey = null;
  }

  /** Load a theme by ID or config object. Rebuilds tile cache. */
  setTheme(themeOrId, tileSize = 48) {
    this.theme = typeof themeOrId === 'string' ? (BUILT_IN_THEMES[themeOrId] || BUILT_IN_THEMES.bleeding_catacombs) : themeOrId;
    this.tileSize = tileSize;
    this._buildCache();
    this._ready = true;

    // Invalidate fog offscreen cache on theme change
    this._fogCanvas = null;
    this._fogCacheKey = null;
  }

  isReady() { return this._ready && this.theme !== null; }
  getTheme() { return this.theme; }
  getThemeId() { return this.theme?.id || null; }

  /** Get all available built-in theme IDs. */
  static getThemeIds() { return Object.keys(BUILT_IN_THEMES); }
  static getThemes() { return BUILT_IN_THEMES; }

  /**
   * Draw a themed tile. Returns true if drawn.
   * @param {CanvasRenderingContext2D} ctx
   * @param {string} tileType - wall/floor/corridor/spawn/door/chest/stairs
   * @param {number} px - Pixel X
   * @param {number} py - Pixel Y
   * @param {number} gridX - Grid coordinate X
   * @param {number} gridY - Grid coordinate Y
   * @param {Object} extra - { doorOpen, chestOpened }
   */
  drawTile(ctx, tileType, px, py, gridX, gridY, extra = {}) {
    if (!this._ready) return false;

    // Cached tile types
    if (tileType === 'wall' || tileType === 'floor' || tileType === 'corridor' || tileType === 'spawn') {
      const key = `${tileType}_${this._variant(gridX, gridY)}`;
      const cached = this.cache.get(key);
      if (cached) { ctx.drawImage(cached, px, py); return true; }
    }

    // State-dependent tiles drawn directly
    const s = this.tileSize, seed = this._seed(gridX, gridY), pal = this.theme.palette;
    switch (tileType) {
      case 'door': {
        drawCorridor(ctx, px, py, s, seed, pal, this.theme);
        const isOpen = extra.doorOpen === true;
        if (isOpen) {
          const dc = lerpColor(pal.accent, '#8B4513', 0.5);
          ctx.strokeStyle = dc; ctx.lineWidth = 2; ctx.strokeRect(px + 4, py + 4, s - 8, s - 8);
          ctx.fillStyle = dc; ctx.font = `${s * 0.22}px sans-serif`; ctx.textAlign = 'center';
          ctx.fillText('○', px + s / 2, py + s / 2 + s * 0.08);
        } else {
          const wd = lerpColor(pal.secondary, '#5C3310', 0.6), wl = lerpColor(pal.secondary, '#8B4513', 0.5);
          ctx.fillStyle = wd; ctx.fillRect(px + 4, py + 4, s - 8, s - 8);
          ctx.strokeStyle = wl; ctx.lineWidth = 0.5;
          for (let i = 0; i < 3; i++) { const ly = py + 8 + i * (s - 16) / 3; ctx.beginPath(); ctx.moveTo(px + 6, ly); ctx.lineTo(px + s - 6, ly); ctx.stroke(); }
          ctx.strokeStyle = shiftColor(wd, -10); ctx.lineWidth = 1; ctx.strokeRect(px + 4, py + 4, s - 8, s - 8);
          ctx.fillStyle = pal.highlight || '#DAA520'; ctx.beginPath(); ctx.arc(px + s / 2 + 6, py + s / 2, 2, 0, Math.PI * 2); ctx.fill();
        }
        return true;
      }
      case 'chest': {
        const floorFn = FLOOR_FN[this.theme.floor.style] || drawFloor_flagstone;
        floorFn(ctx, px, py, s, seed, pal, this.theme.floor);
        const isOpened = extra.chestOpened === true;
        const chestTier = extra.chestTier || 'wooden';
        drawChestIcon(ctx, px, py, s, chestTier, isOpened);
        return true;
      }
      case 'stairs': {
        drawCorridor(ctx, px, py, s, seed, pal, this.theme);
        const sc = lerpColor(pal.accent, '#88CC88', 0.3), bc = shiftColor(sc, -15);
        const stW = s * 0.55, stH = s * 0.12, stX = px + (s - stW) / 2;
        for (let i = 0; i < 3; i++) {
          const sy = py + s * 0.22 + i * (stH + 2), sw = stW - i * 4, sx = stX + i * 2;
          ctx.fillStyle = sc; ctx.fillRect(sx, sy, sw, stH);
          ctx.strokeStyle = bc; ctx.lineWidth = 1; ctx.strokeRect(sx, sy, sw, stH);
        }
        ctx.fillStyle = sc; ctx.font = `${s * 0.3}px sans-serif`; ctx.textAlign = 'center'; ctx.fillText('▼', px + s / 2, py + s - 3);
        return true;
      }
      default: {
        // Fall back to wall
        const key = `wall_${this._variant(gridX, gridY)}`;
        const cached = this.cache.get(key);
        if (cached) { ctx.drawImage(cached, px, py); return true; }
        return false;
      }
    }
  }

  /**
   * Draw wall-edge transitions on a floor tile.
   * @param {CanvasRenderingContext2D} ctx
   * @param {number} px - Pixel X
   * @param {number} py - Pixel Y
   * @param {number} gridX - Grid X
   * @param {number} gridY - Grid Y
   * @param {Object} neighbors - { top, bottom, left, right } — true if wall
   */
  drawEdge(ctx, px, py, gridX, gridY, neighbors) {
    if (!this._ready || !this.theme?.edge) return;
    const ec = this.theme.edge, pal = this.theme.palette;
    const fn = EDGE_FN[ec.style];
    if (!fn) return;
    const s = this.tileSize, seed = this._seed(gridX, gridY);
    if (neighbors.top)    fn(ctx, px, py, s, 'top', seed, pal, ec);
    if (neighbors.bottom) fn(ctx, px, py, s, 'bottom', seed, pal, ec);
    if (neighbors.left)   fn(ctx, px, py, s, 'left', seed, pal, ec);
    if (neighbors.right)  fn(ctx, px, py, s, 'right', seed, pal, ec);
  }

  /**
   * Draw themed fog of war.
   * @param {Map<string,number>|null} fogLightMap — per-tile alpha reduction from nearby light sources
   */
  drawFog(ctx, gridWidth, gridHeight, visibleTiles, offsetX, offsetY, revealedTiles, fogLightMap = null) {
    if (!visibleTiles) return;

    const canvasW = ctx.canvas.width;
    const canvasH = ctx.canvas.height;
    const themeId = this.theme?.id || '';
    const revealedSize = revealedTiles ? revealedTiles.size : 0;

    // P-B: Cache key — visibleTiles.size and revealedTiles.size are O(1) proxies.
    // Both Sets only grow during a floor (tiles get revealed, never un-revealed).
    // offsetX/offsetY included because offscreen canvas is viewport-scoped.
    const newKey = `${themeId}_${visibleTiles.size}_${revealedSize}_${offsetX}_${offsetY}_${canvasW}_${canvasH}`;

    if (this._fogCacheKey === newKey && this._fogCanvas) {
      // Cache hit — single blit
      ctx.drawImage(this._fogCanvas, 0, 0);
      return;
    }

    // Cache miss — render fog to offscreen canvas
    if (!this._fogCanvas || this._fogCanvas.width !== canvasW || this._fogCanvas.height !== canvasH) {
      this._fogCanvas = document.createElement('canvas');
      this._fogCanvas.width = canvasW;
      this._fogCanvas.height = canvasH;
    }

    const offCtx = this._fogCanvas.getContext('2d');
    offCtx.clearRect(0, 0, canvasW, canvasH);

    const fog = this.theme?.fog || {};
    const eTint = fog.exploredTint || 'rgba(0,0,0,0.6)';
    const uColor = fog.unexploredColor || 'rgba(0,0,0,1.0)';

    // Parse the base explored alpha from the theme tint string
    let baseExploredAlpha = 0.6;
    const alphaMatch = eTint.match(/[\d.]+\)$/);
    if (alphaMatch) baseExploredAlpha = parseFloat(alphaMatch[0]);

    // Parse RGB components from explored tint for light-modulated tiles
    let eTintR = 0, eTintG = 0, eTintB = 0;
    const rgbMatch = eTint.match(/rgba?\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)/);
    if (rgbMatch) { eTintR = parseInt(rgbMatch[1]); eTintG = parseInt(rgbMatch[2]); eTintB = parseInt(rgbMatch[3]); }

    // Only iterate tiles visible in the current viewport (not the full grid)
    const tilesVisibleX = Math.ceil(canvasW / this.tileSize) + 1;
    const tilesVisibleY = Math.ceil(canvasH / this.tileSize) + 1;
    const startX = Math.max(0, Math.floor(offsetX));
    const startY = Math.max(0, Math.floor(offsetY));
    const endX = Math.min(gridWidth, startX + tilesVisibleX);
    const endY = Math.min(gridHeight, startY + tilesVisibleY);

    for (let x = startX; x < endX; x++) {
      for (let y = startY; y < endY; y++) {
        const key = `${x},${y}`;
        if (visibleTiles.has(key)) continue;

        const isRevealed = revealedTiles && revealedTiles.has(key);
        if (isRevealed) {
          // Modulate fog alpha near light sources on revealed tiles
          const lightReduction = fogLightMap ? (fogLightMap.get(key) || 0) : 0;
          const alpha = Math.max(0.15, baseExploredAlpha - lightReduction);
          offCtx.fillStyle = `rgba(${eTintR}, ${eTintG}, ${eTintB}, ${alpha.toFixed(3)})`;
        } else {
          offCtx.fillStyle = revealedTiles ? uColor : 'rgba(0,0,0,0.7)';
        }
        offCtx.fillRect((x - offsetX) * this.tileSize, (y - offsetY) * this.tileSize, this.tileSize, this.tileSize);
      }
    }

    this._fogCacheKey = newKey;

    // Blit to the main canvas
    ctx.drawImage(this._fogCanvas, 0, 0);
  }

  // ── Internal ──

  _buildCache() {
    this.cache.clear();
    if (!this.theme) return;
    const s = this.tileSize, pal = this.theme.palette;
    const wFn = WALL_FN[this.theme.wall?.style] || drawWall_crackedStone;
    const fFn = FLOOR_FN[this.theme.floor?.style] || drawFloor_flagstone;
    for (let v = 0; v < VARIANTS; v++) {
      let c = this._mkCanvas(s); wFn(c.getContext('2d'), 0, 0, s, v * 137, pal, this.theme.wall); this.cache.set(`wall_${v}`, c);
      c = this._mkCanvas(s); fFn(c.getContext('2d'), 0, 0, s, v * 251, pal, this.theme.floor); this.cache.set(`floor_${v}`, c);
      c = this._mkCanvas(s); drawCorridor(c.getContext('2d'), 0, 0, s, v * 349, pal, this.theme); this.cache.set(`corridor_${v}`, c);
      c = this._mkCanvas(s); drawSpawn(c.getContext('2d'), 0, 0, s, v * 503, pal, this.theme); this.cache.set(`spawn_${v}`, c);
    }
  }

  _mkCanvas(s) {
    if (typeof OffscreenCanvas !== 'undefined') return new OffscreenCanvas(s, s);
    const c = document.createElement('canvas'); c.width = s; c.height = s; return c;
  }

  _variant(gx, gy) { return Math.floor(cellHash(gx, gy, 0) * VARIANTS); }
  _seed(gx, gy) { return ((gx * 7919) + (gy * 6271)) & 0x7FFFFFFF; }
}

/**
 * Singleton instance for game use.
 * Import in dungeonRenderer.js: import { themeEngine } from './ThemeEngine.js';
 */
export const themeEngine = new ThemeEngine();
