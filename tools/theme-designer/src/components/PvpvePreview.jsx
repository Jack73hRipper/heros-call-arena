// ─────────────────────────────────────────────────────────
// PvpvePreview.jsx — PVPVE dungeon preview center panel
//
// Renders a WFC-generated PVPVE dungeon with the active
// theme applied. Supports toggleable overlay layers for
// module grid, spawn zones, boss highlight, difficulty
// tiers, and room labels. Zoom and hover info included.
// ─────────────────────────────────────────────────────────

import React, { useRef, useEffect, useState, useCallback, useMemo } from 'react';
import { ThemeRenderer } from '../engine/themeRenderer.js';
import { TILE_LEGEND } from '../engine/sampleMaps.js';
import { drawRoomOverlay, ROOM_ARCHETYPES, computeOverlayDecorations } from '../engine/roomArchetypes.js';
import { getTheme } from '../engine/themes.js';
import { generatePvpveDungeon } from '../engine/pvpveGenerator.js';
import { computeRoomPropMap } from '../engine/tileProps.js';

const BASE_TILE_SIZE = 48;
const MODULE_SIZE = 8;

// ─── Team Colors ─────────────────────────────────────────

const TEAM_COLORS = {
  a: { fill: 'rgba(60, 120, 255, 0.18)', stroke: 'rgba(60, 120, 255, 0.7)',  label: '#5599ff' },
  b: { fill: 'rgba(255, 60, 60, 0.18)',  stroke: 'rgba(255, 60, 60, 0.7)',   label: '#ff5555' },
  c: { fill: 'rgba(60, 220, 60, 0.18)',  stroke: 'rgba(60, 220, 60, 0.7)',   label: '#55dd55' },
  d: { fill: 'rgba(255, 220, 40, 0.18)', stroke: 'rgba(255, 220, 40, 0.7)',  label: '#ffdd44' },
};

// ─── Difficulty Tier Colors ──────────────────────────────

const TIER_COLORS = {
  boss:   'rgba(255, 200, 40, 0.15)',
  elite:  'rgba(220, 40, 40, 0.12)',
  hard:   'rgba(220, 140, 30, 0.10)',
  normal: 'rgba(0, 0, 0, 0)',
};

const TIER_BORDER_COLORS = {
  boss:   'rgba(255, 200, 40, 0.6)',
  elite:  'rgba(220, 40, 40, 0.4)',
  hard:   'rgba(220, 140, 30, 0.3)',
  normal: 'rgba(0, 0, 0, 0)',
};

// ─── Extended Tile Legend (E and B render as floor) ──────

const PVPVE_TILE_LEGEND = {
  ...TILE_LEGEND,
  'E': 'floor',
  'B': 'floor',
};

// ─────────────────────────────────────────────────────────
//  Component
// ─────────────────────────────────────────────────────────

export default function PvpvePreview({ themeId, gridRows, gridCols, teamCount, seed }) {
  const canvasRef = useRef(null);
  const rendererRef = useRef(new ThemeRenderer());
  const [zoom, setZoom] = useState(0.6);
  const [hoverTile, setHoverTile] = useState(null);

  // Overlay toggles
  const [showModuleGrid, setShowModuleGrid] = useState(true);
  const [showSpawnZones, setShowSpawnZones] = useState(true);
  const [showBossHighlight, setShowBossHighlight] = useState(true);
  const [showDifficultyTiers, setShowDifficultyTiers] = useState(false);
  const [showRoomLabels, setShowRoomLabels] = useState(false);

  // ── Generate dungeon (memoized on config change) ──────

  const dungeon = useMemo(() => {
    return generatePvpveDungeon({ seed, gridRows, gridCols, teamCount });
  }, [seed, gridRows, gridCols, teamCount]);

  const tileSize = Math.round(BASE_TILE_SIZE * zoom);

  // ── Build room lookup for hover info ──────────────────

  const roomLookup = useMemo(() => {
    if (!dungeon.success || !dungeon.rooms) return {};
    const lookup = {};
    for (const room of dungeon.rooms) {
      if (!room.bounds) continue;
      for (let y = room.bounds.y_min; y <= room.bounds.y_max; y++) {
        for (let x = room.bounds.x_min; x <= room.bounds.x_max; x++) {
          lookup[`${x},${y}`] = room;
        }
      }
    }
    return lookup;
  }, [dungeon]);

  // ── Build prop lookup for hover info ──────────────────

  const propLookup = useMemo(() => {
    if (!dungeon.success || !dungeon.rooms) return new Map();
    const theme = getTheme(themeId);
    if (!theme) return new Map();

    const tileMap = dungeon.tileMap;
    const mapH = tileMap.length;
    const mapW = tileMap[0]?.length || 0;

    // Build walkable tile set
    const walkableTiles = new Set();
    for (let y = 0; y < mapH; y++) {
      for (let x = 0; x < mapW; x++) {
        const tileType = PVPVE_TILE_LEGEND[tileMap[y][x]] || 'wall';
        if (tileType !== 'wall') walkableTiles.add(`${x},${y}`);
      }
    }

    const merged = new Map();
    for (const room of dungeon.rooms) {
      const archetype = room.archetype || room.role;
      if (!archetype || !room.bounds) continue;

      const doorPositions = (dungeon.doors || [])
        .filter(d => d.x >= room.bounds.x_min && d.x <= room.bounds.x_max
                  && d.y >= room.bounds.y_min && d.y <= room.bounds.y_max);

      const b = room.bounds;
      let fxMin = b.x_max, fyMin = b.y_max, fxMax = b.x_min, fyMax = b.y_min;
      for (let ry = b.y_min; ry <= b.y_max; ry++) {
        for (let rx = b.x_min; rx <= b.x_max; rx++) {
          if (walkableTiles.has(`${rx},${ry}`)) {
            if (rx < fxMin) fxMin = rx;
            if (rx > fxMax) fxMax = rx;
            if (ry < fyMin) fyMin = ry;
            if (ry > fyMax) fyMax = ry;
          }
        }
      }
      const inner = fxMax >= fxMin
        ? { x_min: fxMin, y_min: fyMin, x_max: fxMax, y_max: fyMax }
        : { x_min: b.x_min + 1, y_min: b.y_min + 1, x_max: b.x_max - 1, y_max: b.y_max - 1 };

      const roomProps = computeRoomPropMap({
        archetype,
        theme,
        bounds: inner,
        seed: seed + (room.id ? room.id.charCodeAt(5) || 0 : 0),
        doorPositions,
        walkableTiles,
      });

      for (const [key, propName] of roomProps) {
        merged.set(key, propName);
      }
    }
    return merged;
  }, [dungeon, themeId, seed]);

  // ── Build overlay decoration lookup for hover info ────

  const overlayLookup = useMemo(() => {
    if (!dungeon.success || !dungeon.rooms) return new Map();
    const tileMap = dungeon.tileMap;
    const mapH = tileMap.length;
    const mapW = tileMap[0]?.length || 0;

    const walkableTiles = new Set();
    for (let y = 0; y < mapH; y++) {
      for (let x = 0; x < mapW; x++) {
        const tileType = PVPVE_TILE_LEGEND[tileMap[y][x]] || 'wall';
        if (tileType !== 'wall') walkableTiles.add(`${x},${y}`);
      }
    }

    const merged = new Map();
    for (const room of dungeon.rooms) {
      const archetype = room.archetype || room.role;
      if (!archetype || !room.bounds) continue;

      const doorPositions = (dungeon.doors || [])
        .filter(d => d.x >= room.bounds.x_min && d.x <= room.bounds.x_max
                  && d.y >= room.bounds.y_min && d.y <= room.bounds.y_max);

      const b = room.bounds;
      let fxMin = b.x_max, fyMin = b.y_max, fxMax = b.x_min, fyMax = b.y_min;
      for (let ry = b.y_min; ry <= b.y_max; ry++) {
        for (let rx = b.x_min; rx <= b.x_max; rx++) {
          if (walkableTiles.has(`${rx},${ry}`)) {
            if (rx < fxMin) fxMin = rx;
            if (rx > fxMax) fxMax = rx;
            if (ry < fyMin) fyMin = ry;
            if (ry > fyMax) fyMax = ry;
          }
        }
      }
      const inner = fxMax >= fxMin
        ? { x_min: fxMin, y_min: fyMin, x_max: fxMax, y_max: fyMax }
        : { x_min: b.x_min + 1, y_min: b.y_min + 1, x_max: b.x_max - 1, y_max: b.y_max - 1 };

      const overlayDecos = computeOverlayDecorations(
        archetype, inner, doorPositions,
        seed + (room.id ? room.id.charCodeAt(5) || 0 : 0),
      );

      for (const [key, label] of overlayDecos) {
        merged.set(key, label);
      }
    }
    return merged;
  }, [dungeon, seed]);

  // ── Render ────────────────────────────────────────────

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas || !dungeon.success) return;

    const ctx = canvas.getContext('2d');
    const renderer = rendererRef.current;
    const tileMap = dungeon.tileMap;
    const mapH = tileMap.length;
    const mapW = tileMap[0]?.length || 0;

    renderer.setTheme(themeId, tileSize);
    const theme = getTheme(themeId);

    const canvasW = mapW * tileSize;
    const canvasH = mapH * tileSize;
    canvas.width = canvasW;
    canvas.height = canvasH;

    // Clear
    ctx.fillStyle = '#0a0a12';
    ctx.fillRect(0, 0, canvasW, canvasH);

    // Helper: resolve tile type at grid position for neighbor detection
    const _tileType = (gx, gy) => {
      if (gy < 0 || gy >= mapH || gx < 0 || gx >= mapW) return 'wall';
      return PVPVE_TILE_LEGEND[tileMap[gy][gx]] || 'wall';
    };

    // ── Layer 1: Base tiles ──
    for (let y = 0; y < mapH; y++) {
      const row = tileMap[y];
      for (let x = 0; x < mapW; x++) {
        const ch = row[x];
        const tileType = PVPVE_TILE_LEGEND[ch] || 'wall';
        const px = x * tileSize;
        const py = y * tileSize;

        const extra = {};
        if (tileType === 'door') {
          extra.doorOpen = false;
          extra.wallNorth = _tileType(x, y - 1) === 'wall';
          extra.wallSouth = _tileType(x, y + 1) === 'wall';
          extra.wallEast  = _tileType(x + 1, y) === 'wall';
          extra.wallWest  = _tileType(x - 1, y) === 'wall';
        }
        if (tileType === 'chest') extra.chestOpened = false;

        renderer.drawTile(ctx, tileType, px, py, x, y, extra);

        // ── Enemy marker (subtle red diamond) ──
        if (ch === 'E') {
          _drawEnemyMarker(ctx, px, py, tileSize);
        }
        // ── Boss marker (gold crown) ──
        if (ch === 'B') {
          _drawBossMarker(ctx, px, py, tileSize);
        }
      }
    }

    // ── Layer 2: Room archetype overlays ──
    if (theme && dungeon.rooms) {
      // Build walkable tile set from tileMap
      const walkableTiles = new Set();
      for (let y = 0; y < mapH; y++) {
        for (let x = 0; x < mapW; x++) {
          const tileType = PVPVE_TILE_LEGEND[tileMap[y][x]] || 'wall';
          if (tileType !== 'wall') walkableTiles.add(`${x},${y}`);
        }
      }

      for (const room of dungeon.rooms) {
        const archetype = room.archetype || room.role;
        if (!archetype || !room.bounds) continue;

        const doorPositions = (dungeon.doors || [])
          .filter(d => d.x >= room.bounds.x_min && d.x <= room.bounds.x_max
                    && d.y >= room.bounds.y_min && d.y <= room.bounds.y_max);

        // Compute tight floor_bounds by scanning actual non-wall tiles
        const b = room.bounds;
        let fxMin = b.x_max, fyMin = b.y_max, fxMax = b.x_min, fyMax = b.y_min;
        for (let ry = b.y_min; ry <= b.y_max; ry++) {
          for (let rx = b.x_min; rx <= b.x_max; rx++) {
            if (walkableTiles.has(`${rx},${ry}`)) {
              if (rx < fxMin) fxMin = rx;
              if (rx > fxMax) fxMax = rx;
              if (ry < fyMin) fyMin = ry;
              if (ry > fyMax) fyMax = ry;
            }
          }
        }
        const inner = fxMax >= fxMin
          ? { x_min: fxMin, y_min: fyMin, x_max: fxMax, y_max: fyMax }
          : { x_min: b.x_min + 1, y_min: b.y_min + 1, x_max: b.x_max - 1, y_max: b.y_max - 1 };

        drawRoomOverlay(ctx, {
          archetype,
          theme,
          tileSize,
          roomOffsetX: 0,
          roomOffsetY: 0,
          roomWidth: room.bounds.x_max - room.bounds.x_min + 1,
          roomHeight: room.bounds.y_max - room.bounds.y_min + 1,
          bounds: inner,
          doorPositions,
          walkableTiles,
          seed: seed + (room.id ? room.id.charCodeAt(5) || 0 : 0),
        });
      }
    }

    // ── Layer 3: Module grid overlay ──
    if (showModuleGrid) {
      ctx.strokeStyle = 'rgba(255, 255, 255, 0.12)';
      ctx.lineWidth = 1;
      ctx.setLineDash([4, 4]);

      for (let r = 1; r < dungeon.gridRows; r++) {
        const py = r * MODULE_SIZE * tileSize;
        ctx.beginPath();
        ctx.moveTo(0, py);
        ctx.lineTo(canvasW, py);
        ctx.stroke();
      }
      for (let c = 1; c < dungeon.gridCols; c++) {
        const px = c * MODULE_SIZE * tileSize;
        ctx.beginPath();
        ctx.moveTo(px, 0);
        ctx.lineTo(px, canvasH);
        ctx.stroke();
      }

      ctx.setLineDash([]);
    }

    // ── Layer 4: Team spawn zone highlights ──
    if (showSpawnZones && dungeon.spawnZones) {
      for (const [teamKey, zone] of Object.entries(dungeon.spawnZones)) {
        const colors = TEAM_COLORS[teamKey];
        if (!colors || !zone) continue;
        const zx = zone.x_min * tileSize;
        const zy = zone.y_min * tileSize;
        const zw = (zone.x_max - zone.x_min + 1) * tileSize;
        const zh = (zone.y_max - zone.y_min + 1) * tileSize;

        ctx.fillStyle = colors.fill;
        ctx.fillRect(zx, zy, zw, zh);
        ctx.strokeStyle = colors.stroke;
        ctx.lineWidth = 2;
        ctx.strokeRect(zx + 1, zy + 1, zw - 2, zh - 2);

        // Team label
        ctx.fillStyle = colors.label;
        ctx.font = `bold ${Math.max(10, tileSize * 0.6)}px sans-serif`;
        ctx.textAlign = 'center';
        ctx.textBaseline = 'middle';
        ctx.fillText(`Team ${teamKey.toUpperCase()}`, zx + zw / 2, zy + zh / 2);
      }
    }

    // ── Layer 5: Boss room highlight ──
    if (showBossHighlight && dungeon.bossRoom?.bounds) {
      const b = dungeon.bossRoom.bounds;
      const bx = b.x_min * tileSize;
      const by = b.y_min * tileSize;
      const bw = (b.x_max - b.x_min + 1) * tileSize;
      const bh = (b.y_max - b.y_min + 1) * tileSize;

      // Gold glow
      ctx.shadowColor = 'rgba(255, 200, 40, 0.5)';
      ctx.shadowBlur = 12;
      ctx.strokeStyle = 'rgba(255, 200, 40, 0.7)';
      ctx.lineWidth = 3;
      ctx.strokeRect(bx + 2, by + 2, bw - 4, bh - 4);
      ctx.shadowColor = 'transparent';
      ctx.shadowBlur = 0;

      // Boss label
      ctx.fillStyle = 'rgba(255, 200, 40, 0.9)';
      ctx.font = `bold ${Math.max(11, tileSize * 0.5)}px sans-serif`;
      ctx.textAlign = 'center';
      ctx.textBaseline = 'top';
      ctx.fillText('★ BOSS ★', bx + bw / 2, by + 4);
    }

    // ── Layer 6: Difficulty tier overlay ──
    if (showDifficultyTiers && dungeon.rooms) {
      for (const room of dungeon.rooms) {
        if (!room.bounds || !room.difficultyTier) continue;
        const tier = room.difficultyTier;
        const fillColor = TIER_COLORS[tier];
        const borderColor = TIER_BORDER_COLORS[tier];
        if (!fillColor || fillColor === 'rgba(0, 0, 0, 0)') continue;

        const rx = room.bounds.x_min * tileSize;
        const ry = room.bounds.y_min * tileSize;
        const rw = (room.bounds.x_max - room.bounds.x_min + 1) * tileSize;
        const rh = (room.bounds.y_max - room.bounds.y_min + 1) * tileSize;

        ctx.fillStyle = fillColor;
        ctx.fillRect(rx, ry, rw, rh);
        if (borderColor) {
          ctx.strokeStyle = borderColor;
          ctx.lineWidth = 1;
          ctx.strokeRect(rx, ry, rw, rh);
        }
      }
    }

    // ── Layer 7: Room labels ──
    if (showRoomLabels && zoom >= 0.8 && dungeon.rooms) {
      ctx.textAlign = 'center';
      ctx.textBaseline = 'middle';
      const fontSize = Math.max(9, Math.min(14, tileSize * 0.35));
      ctx.font = `600 ${fontSize}px sans-serif`;

      for (const room of dungeon.rooms) {
        if (!room.bounds) continue;

        const rx = room.bounds.x_min * tileSize;
        const ry = room.bounds.y_min * tileSize;
        const rw = (room.bounds.x_max - room.bounds.x_min + 1) * tileSize;
        const rh = (room.bounds.y_max - room.bounds.y_min + 1) * tileSize;
        const cx = rx + rw / 2;
        const cy = ry + rh / 2;

        const role = room.role || '???';
        const arch = room.archetype;
        const team = room.team;
        let label = role.charAt(0).toUpperCase() + role.slice(1);
        if (team) label = `Spawn ${team.toUpperCase()}`;
        if (arch && arch !== role) label += ` / ${arch.charAt(0).toUpperCase() + arch.slice(1)}`;

        // Background pill
        const metrics = ctx.measureText(label);
        const pw = metrics.width + 8;
        const ph = fontSize + 6;
        ctx.fillStyle = 'rgba(0, 0, 0, 0.65)';
        ctx.beginPath();
        _roundRect(ctx, cx - pw / 2, cy - ph / 2, pw, ph, 3);
        ctx.fill();

        // Text
        ctx.fillStyle = 'rgba(255, 255, 255, 0.85)';
        ctx.fillText(label, cx, cy);
      }
    }

    // ── Hover highlight ──
    if (hoverTile) {
      ctx.strokeStyle = 'rgba(255, 255, 255, 0.4)';
      ctx.lineWidth = 2;
      ctx.strokeRect(
        hoverTile.x * tileSize + 1,
        hoverTile.y * tileSize + 1,
        tileSize - 2,
        tileSize - 2
      );
    }
  }, [themeId, tileSize, dungeon, seed, hoverTile,
      showModuleGrid, showSpawnZones, showBossHighlight,
      showDifficultyTiers, showRoomLabels, zoom]);

  // ── Mouse tracking ────────────────────────────────────

  const handleMouseMove = useCallback((e) => {
    const canvas = canvasRef.current;
    if (!canvas || !dungeon.success) return;

    const rect = canvas.getBoundingClientRect();
    const mx = e.clientX - rect.left;
    const my = e.clientY - rect.top;
    const gx = Math.floor(mx / tileSize);
    const gy = Math.floor(my / tileSize);

    const tileMap = dungeon.tileMap;
    const mapH = tileMap.length;
    const mapW = tileMap[0]?.length || 0;

    if (gx >= 0 && gx < mapW && gy >= 0 && gy < mapH) {
      const ch = tileMap[gy]?.[gx];
      const room = roomLookup[`${gx},${gy}`] || null;
      const moduleRow = Math.floor(gy / MODULE_SIZE);
      const moduleCol = Math.floor(gx / MODULE_SIZE);
      const propName = propLookup.get(`${gx},${gy}`) || null;
      const overlayDeco = overlayLookup.get(`${gx},${gy}`) || null;

      setHoverTile({
        x: gx,
        y: gy,
        char: ch,
        type: PVPVE_TILE_LEGEND[ch] || 'wall',
        moduleRow,
        moduleCol,
        room,
        propName,
        overlayDeco,
      });
    } else {
      setHoverTile(null);
    }
  }, [dungeon, tileSize, roomLookup, propLookup, overlayLookup]);

  const handleMouseLeave = useCallback(() => {
    setHoverTile(null);
  }, []);

  // ── Error state ───────────────────────────────────────

  if (!dungeon.success) {
    return (
      <div className="dungeon-preview">
        <div className="pvpve-error">
          <span className="pvpve-error-icon">⚠</span>
          <span>WFC generation failed — try a different seed</span>
          {dungeon.error && <span className="pvpve-error-detail">{dungeon.error}</span>}
        </div>
      </div>
    );
  }

  // ── Hover info string (status bar) ─────────────────────

  let hoverInfoStr = '';
  if (hoverTile) {
    hoverInfoStr = `[${hoverTile.x}, ${hoverTile.y}] ${hoverTile.type} (${hoverTile.char})`;
    hoverInfoStr += ` — Module [${hoverTile.moduleRow}, ${hoverTile.moduleCol}]`;
    if (hoverTile.propName) hoverInfoStr += ` — Prop: ${hoverTile.propName}`;
    if (hoverTile.room) {
      const r = hoverTile.room;
      hoverInfoStr += ` — ${r.role || '?'}`;
      if (r.archetype && r.archetype !== r.role) hoverInfoStr += `/${r.archetype}`;
      if (r.difficultyTier) hoverInfoStr += ` (${r.difficultyTier})`;
      if (r.team) hoverInfoStr += ` [Team ${r.team.toUpperCase()}]`;
      if (r.enemyCount > 0) hoverInfoStr += ` enemies:${r.enemyCount}`;
    }
  }

  // ── Build hover tooltip data ──────────────────────────

  const hoverTooltip = useMemo(() => {
    if (!hoverTile) return null;
    const t = hoverTile;
    const tooltip = {
      position: `${t.x}, ${t.y}`,
      tileType: t.type,
      tileChar: t.char,
      module: `${t.moduleRow}, ${t.moduleCol}`,
      propName: t.propName ? _formatPropName(t.propName) : null,
      propId: t.propName || null,
      overlayDeco: t.overlayDeco || null,
    };

    if (t.room) {
      const r = t.room;
      tooltip.roomRole = r.role;
      tooltip.roomArchetype = r.archetype || r.role;
      tooltip.roomTier = r.difficultyTier || null;
      tooltip.roomTeam = r.team ? r.team.toUpperCase() : null;
      tooltip.roomEnemies = r.enemyCount || 0;
      tooltip.roomChests = r.chestCount || 0;
      tooltip.roomSource = r.sourceName || null;
      // Archetype label & description from ROOM_ARCHETYPES
      const archInfo = ROOM_ARCHETYPES[tooltip.roomArchetype];
      tooltip.archetypeLabel = archInfo?.label || null;
      tooltip.archetypeDesc = archInfo?.description || null;
    }

    return tooltip;
  }, [hoverTile]);

  // ── Stats summary ─────────────────────────────────────

  const stats = dungeon.stats || {};
  const roomCount = dungeon.rooms?.length || 0;
  const doorCount = dungeon.doors?.length || 0;
  const spawnCount = Object.keys(dungeon.spawnZones || {}).length;

  return (
    <div className="dungeon-preview">
      <div className="preview-controls">
        <label>Zoom:</label>
        <input
          type="range"
          min="0.3"
          max="2"
          step="0.1"
          value={zoom}
          onChange={e => setZoom(parseFloat(e.target.value))}
        />
        <span>{Math.round(zoom * 100)}%</span>

        <span className="pvpve-stats">
          {roomCount} rooms · {doorCount} doors · {spawnCount} spawns
          {stats.enemies != null && ` · ${stats.enemies} enemies`}
        </span>

        {hoverTile && (
          <span className="hover-info">{hoverInfoStr}</span>
        )}
      </div>

      {/* Overlay toggle panel */}
      <div className="pvpve-overlay-toggles">
        <label>
          <input type="checkbox" checked={showModuleGrid}
            onChange={e => setShowModuleGrid(e.target.checked)} />
          Module Grid
        </label>
        <label>
          <input type="checkbox" checked={showSpawnZones}
            onChange={e => setShowSpawnZones(e.target.checked)} />
          Spawn Zones
        </label>
        <label>
          <input type="checkbox" checked={showBossHighlight}
            onChange={e => setShowBossHighlight(e.target.checked)} />
          Boss Highlight
        </label>
        <label>
          <input type="checkbox" checked={showDifficultyTiers}
            onChange={e => setShowDifficultyTiers(e.target.checked)} />
          Difficulty Tiers
        </label>
        <label>
          <input type="checkbox" checked={showRoomLabels}
            onChange={e => setShowRoomLabels(e.target.checked)} />
          Room Labels
        </label>
      </div>

      <div className="preview-canvas-wrap">
        <canvas
          ref={canvasRef}
          onMouseMove={handleMouseMove}
          onMouseLeave={handleMouseLeave}
          style={{ imageRendering: 'pixelated', cursor: 'crosshair' }}
        />
      </div>

      {/* Fixed tile info panel — always visible, never follows cursor */}
      <div className="pvpve-hover-tooltip">
        {hoverTooltip ? (
          <>
            <div className="tooltip-header">
              <span className="tooltip-pos">[{hoverTooltip.position}]</span>
              <span className={`tooltip-tile-type tile-${hoverTooltip.tileType}`}>
                {hoverTooltip.tileType}
              </span>
              <span className="tooltip-char">({hoverTooltip.tileChar})</span>
              <span className="tooltip-module">Module [{hoverTooltip.module}]</span>
            </div>

            {(hoverTooltip.propName || hoverTooltip.overlayDeco) && (
              <div className="tooltip-row tooltip-prop">
                <span className="tooltip-label">Decoration:</span>
                {hoverTooltip.propName && (
                  <span className="tooltip-prop-name">{hoverTooltip.propName}</span>
                )}
                {hoverTooltip.overlayDeco && (
                  <span className="tooltip-overlay-name">{hoverTooltip.overlayDeco}</span>
                )}
                {hoverTooltip.propId && !hoverTooltip.overlayDeco && (
                  <span className="tooltip-prop-id">({hoverTooltip.propId})</span>
                )}
              </div>
            )}

            {hoverTooltip.roomRole && (
              <>
                <div className="tooltip-divider" />
                <div className="tooltip-row">
                  <span className="tooltip-label">Room:</span>
                  <span className={`tooltip-role role-${hoverTooltip.roomRole}`}>
                    {hoverTooltip.roomRole}
                  </span>
                  {hoverTooltip.archetypeLabel && (
                    <span className="tooltip-archetype"> / {hoverTooltip.archetypeLabel}</span>
                  )}
                </div>

                {hoverTooltip.archetypeDesc && (
                  <div className="tooltip-desc">{hoverTooltip.archetypeDesc}</div>
                )}

                <div className="tooltip-row">
                  {hoverTooltip.roomTier && (
                    <span className={`tooltip-tier tier-${hoverTooltip.roomTier}`}>
                      {hoverTooltip.roomTier}
                    </span>
                  )}
                  {hoverTooltip.roomTeam && (
                    <span className={`tooltip-team team-${hoverTooltip.roomTeam.toLowerCase()}`}>
                      Team {hoverTooltip.roomTeam}
                    </span>
                  )}
                  {hoverTooltip.roomEnemies > 0 && (
                    <span className="tooltip-enemies">⚔ {hoverTooltip.roomEnemies}</span>
                  )}
                  {hoverTooltip.roomChests > 0 && (
                    <span className="tooltip-chests">📦 {hoverTooltip.roomChests}</span>
                  )}
                </div>

                {hoverTooltip.roomSource && (
                  <div className="tooltip-row tooltip-source">
                    <span className="tooltip-label">Source:</span>
                    <span>{hoverTooltip.roomSource}</span>
                  </div>
                )}
              </>
            )}
          </>
        ) : (
          <div className="tooltip-placeholder">Hover over a tile for details</div>
        )}
      </div>
    </div>
  );
}

// ─── Helper: Format prop ID to display name ─────────────

function _formatPropName(propId) {
  return propId
    .split('_')
    .map(w => w.charAt(0).toUpperCase() + w.slice(1))
    .join(' ');
}

// ─── Canvas Helper: Enemy Marker ─────────────────────────

function _drawEnemyMarker(ctx, px, py, s) {
  const cx = px + s / 2;
  const cy = py + s / 2;
  const r = s * 0.22;

  ctx.fillStyle = 'rgba(200, 40, 40, 0.6)';
  ctx.beginPath();
  ctx.moveTo(cx, cy - r);
  ctx.lineTo(cx + r, cy);
  ctx.lineTo(cx, cy + r);
  ctx.lineTo(cx - r, cy);
  ctx.closePath();
  ctx.fill();

  ctx.strokeStyle = 'rgba(255, 80, 80, 0.8)';
  ctx.lineWidth = 1;
  ctx.stroke();
}

// ─── Canvas Helper: Boss Marker ──────────────────────────

function _drawBossMarker(ctx, px, py, s) {
  const cx = px + s / 2;
  const cy = py + s / 2;
  const r = s * 0.28;

  // Gold diamond
  ctx.fillStyle = 'rgba(255, 200, 40, 0.7)';
  ctx.beginPath();
  ctx.moveTo(cx, cy - r);
  ctx.lineTo(cx + r, cy);
  ctx.lineTo(cx, cy + r);
  ctx.lineTo(cx - r, cy);
  ctx.closePath();
  ctx.fill();

  ctx.strokeStyle = 'rgba(255, 220, 60, 0.9)';
  ctx.lineWidth = 1.5;
  ctx.stroke();

  // Small crown points
  const cr = s * 0.12;
  ctx.fillStyle = 'rgba(255, 220, 60, 0.9)';
  ctx.beginPath();
  ctx.moveTo(cx - cr, cy - r * 0.3);
  ctx.lineTo(cx - cr * 0.5, cy - r * 0.7);
  ctx.lineTo(cx, cy - r * 0.3);
  ctx.lineTo(cx + cr * 0.5, cy - r * 0.7);
  ctx.lineTo(cx + cr, cy - r * 0.3);
  ctx.closePath();
  ctx.fill();
}

// ─── Canvas Helper: Rounded Rect ─────────────────────────

function _roundRect(ctx, x, y, w, h, r) {
  ctx.moveTo(x + r, y);
  ctx.lineTo(x + w - r, y);
  ctx.quadraticCurveTo(x + w, y, x + w, y + r);
  ctx.lineTo(x + w, y + h - r);
  ctx.quadraticCurveTo(x + w, y + h, x + w - r, y + h);
  ctx.lineTo(x + r, y + h);
  ctx.quadraticCurveTo(x, y + h, x, y + h - r);
  ctx.lineTo(x, y + r);
  ctx.quadraticCurveTo(x, y, x + r, y);
}
