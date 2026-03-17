// ─────────────────────────────────────────────────────────
// RoomArchetypePreview.jsx — Room Archetype Visual Preview
//
// Two views:
//   1. Side-by-side isolated rooms — plain vs. each archetype
//   2. Full dungeon map with archetype overlays on labelled rooms
//
// Uses the same ThemeRenderer engine as DungeonPreview.
// ─────────────────────────────────────────────────────────

import React, { useRef, useEffect, useState, useCallback } from 'react';
import { ThemeRenderer } from '../engine/themeRenderer.js';
import { TILE_LEGEND } from '../engine/sampleMaps.js';
import { drawRoomOverlay, ROOM_ARCHETYPES } from '../engine/roomArchetypes.js';

const BASE_TILE_SIZE = 48;

// ─── Isolated room template (8×8) ─────────────────────
const ROOM_TILES = [
  'WWWWDWWW',
  'WFFFFFFW',
  'WFFFFFFW',
  'WFFFFFFW',
  'WFFFFFFW',
  'WFFFFFFW',
  'WFFFFFFW',
  'WWWWWWWW',
].map(row => row.split(''));
const ROOM_W = 8;
const ROOM_H = 8;
const ROOM_BOUNDS = { x_min: 1, y_min: 1, x_max: 6, y_max: 6 };
const DOOR_POSITIONS = [{ x: 4, y: 0 }];

// ─── Full dungeon map (20×27) with labelled rooms ─────
// Each room has a purpose assigned for archetype overlay
const DUNGEON_MAP = [
  'WWWWWWWWWWWWWWWWWWWW',  // 0
  'WWWWSFFSFWWWFFFFFFWW',  // 1
  'WWWWFFFFFFWWFFFFFFWW',  // 2
  'WWWWFFFFFFWWFFFFFFWW',  // 3
  'WWWWFFFFFFWWFFXFFFWW',  // 4
  'WWWWWWDWWWWWWWDWWWWW',  // 5
  'WWWWWWCWWWWWWWCWWWWW',  // 6
  'WWWWWWCCCCCCCCCWWWWW',  // 7
  'WWWWWWCWWWWWWWCWWWWW',  // 8
  'WFFFFFFDWWWWWWCWWWWW',  // 9
  'WFFFFFFWWWWWFFDFWWWW',  // 10
  'WFFFFFFWWWWWFFFFWWWW',  // 11
  'WFFFFFFWWWWWFFFFWWWW',  // 12
  'WWWWDWWWWWWWWWWWWWWW',  // 13
  'WWWWCWWWWWWWWWWWWWWW',  // 14
  'WFFFCFFFWWWWFFFFFFWW',  // 15
  'WFFFFFFFWWWWFFFTFFWW',  // 16
  'WFFFFFFFWWWWFFFFFFWW',  // 17
  'WWWDWWWWWWWWWWWWWWWW',  // 18 — door into shrine
  'WFFFFFFWWWWWFFFFFFWW',  // 19
  'WFFFFFFWWWWWFFFFFFWW',  // 20
  'WFFFFFFWWWWWFFFFFFWW',  // 21
  'WWWDWWWWWWWWWWWWWWWW',  // 22 — door into prison
  'WFFFFFFWWWWWFFFFFFWW',  // 23
  'WFFFFFFWWWWWFFFFFFWW',  // 24
  'WFFFFFFWWWWWFFFFFFWW',  // 25
  'WWWWWWWWWWWWWWWWWWWW',  // 26
].map(row => row.split(''));
const DUNGEON_W = 20;
const DUNGEON_H = 27;

// Room definitions for the dungeon map
const DUNGEON_ROOMS = [
  { id: 'spawn',   purpose: 'spawn',   label: 'Entry Hall',  bounds: { x_min: 4, y_min: 1, x_max: 9, y_max: 4 }, doors: [{ x: 6, y: 5 }] },
  { id: 'loot',    purpose: 'loot',    label: 'Vault',       bounds: { x_min: 12, y_min: 1, x_max: 17, y_max: 4 }, doors: [{ x: 14, y: 5 }] },
  { id: 'enemy',   purpose: 'enemy',   label: 'Barracks',    bounds: { x_min: 1, y_min: 9, x_max: 6, y_max: 12 }, doors: [{ x: 6, y: 9 }, { x: 4, y: 13 }] },
  { id: 'empty',   purpose: 'empty',   label: 'Abandoned',   bounds: { x_min: 12, y_min: 9, x_max: 15, y_max: 12 }, doors: [{ x: 14, y: 9 }] },
  { id: 'boss',    purpose: 'boss',    label: 'Sanctum',     bounds: { x_min: 1, y_min: 15, x_max: 8, y_max: 17 }, doors: [] },
  { id: 'stairs',  purpose: 'stairs',  label: 'Stairwell',   bounds: { x_min: 12, y_min: 15, x_max: 17, y_max: 17 }, doors: [] },
  { id: 'shrine',  purpose: 'shrine',  label: 'Shrine',      bounds: { x_min: 1, y_min: 19, x_max: 6, y_max: 21 }, doors: [{ x: 3, y: 18 }] },
  { id: 'library', purpose: 'library', label: 'Library',     bounds: { x_min: 12, y_min: 19, x_max: 17, y_max: 21 }, doors: [] },
  { id: 'prison',  purpose: 'prison',  label: 'Prison',      bounds: { x_min: 1, y_min: 23, x_max: 6, y_max: 25 }, doors: [{ x: 3, y: 22 }] },
  { id: 'flooded', purpose: 'flooded', label: 'Flooded',     bounds: { x_min: 12, y_min: 23, x_max: 17, y_max: 25 }, doors: [] },
];

export default function RoomArchetypePreview({ themeId }) {
  const isolatedRef = useRef(null);
  const dungeonRef = useRef(null);
  const rendererRef = useRef(new ThemeRenderer());
  const [zoom, setZoom] = useState(1);
  const [activeArchetype, setActiveArchetype] = useState(null);

  const tileSize = Math.round(BASE_TILE_SIZE * zoom);

  // ─── Draw isolated room comparison ──────────────────
  useEffect(() => {
    const canvas = isolatedRef.current;
    if (!canvas) return;

    const ctx = canvas.getContext('2d');
    const renderer = rendererRef.current;
    renderer.setTheme(themeId, tileSize);

    const archetypeKeys = Object.keys(ROOM_ARCHETYPES);
    const cols = archetypeKeys.length + 1;
    const gap = 16;
    const roomPxW = ROOM_W * tileSize;
    const roomPxH = ROOM_H * tileSize;
    const labelH = 28;

    const totalW = cols * roomPxW + (cols - 1) * gap;
    const totalH = roomPxH + labelH;

    canvas.width = totalW;
    canvas.height = totalH;

    ctx.fillStyle = '#0d0d1a';
    ctx.fillRect(0, 0, totalW, totalH);

    const drawRoom = (offX, offY) => {
      for (let y = 0; y < ROOM_H; y++) {
        for (let x = 0; x < ROOM_W; x++) {
          const ch = ROOM_TILES[y][x];
          const tileType = TILE_LEGEND[ch] || 'wall';
          const px = offX + x * tileSize;
          const py = offY + y * tileSize;
          const extra = {};
          if (tileType === 'door') extra.doorOpen = false;
          if (tileType === 'chest') extra.chestOpened = false;
          renderer.drawTile(ctx, tileType, px, py, x, y, extra);
        }
      }
    };

    // Column 0: Plain
    ctx.fillStyle = '#a0a0b0';
    ctx.font = '13px "Segoe UI", sans-serif';
    ctx.textAlign = 'center';
    ctx.fillText('Plain (no overlay)', roomPxW / 2, labelH - 8);
    drawRoom(0, labelH);

    // Columns 1+: Each archetype
    archetypeKeys.forEach((key, i) => {
      const colX = (i + 1) * (roomPxW + gap);
      const archetype = ROOM_ARCHETYPES[key];
      const isActive = activeArchetype === key;
      ctx.fillStyle = isActive ? '#daa520' : '#a0a0b0';
      ctx.font = isActive ? 'bold 13px "Segoe UI", sans-serif' : '13px "Segoe UI", sans-serif';
      ctx.textAlign = 'center';
      ctx.fillText(archetype.label, colX + roomPxW / 2, labelH - 8);
      drawRoom(colX, labelH);
      drawRoomOverlay(ctx, {
        archetype: key,
        theme: renderer.getTheme(),
        tileSize,
        roomOffsetX: colX,
        roomOffsetY: labelH,
        roomWidth: ROOM_W,
        roomHeight: ROOM_H,
        bounds: ROOM_BOUNDS,
        doorPositions: DOOR_POSITIONS,
        seed: 42,
      });
    });
  }, [themeId, tileSize, activeArchetype]);

  // ─── Draw full dungeon with room overlays ───────────
  useEffect(() => {
    const canvas = dungeonRef.current;
    if (!canvas) return;

    const ctx = canvas.getContext('2d');
    const renderer = rendererRef.current;
    renderer.setTheme(themeId, tileSize);

    canvas.width = DUNGEON_W * tileSize;
    canvas.height = DUNGEON_H * tileSize;

    ctx.fillStyle = '#0d0d1a';
    ctx.fillRect(0, 0, canvas.width, canvas.height);

    // Draw base tiles
    for (let y = 0; y < DUNGEON_H; y++) {
      for (let x = 0; x < DUNGEON_W; x++) {
        const ch = DUNGEON_MAP[y][x];
        const tileType = TILE_LEGEND[ch] || 'wall';
        const px = x * tileSize;
        const py = y * tileSize;
        const extra = {};
        if (tileType === 'door') extra.doorOpen = false;
        if (tileType === 'chest') extra.chestOpened = false;
        renderer.drawTile(ctx, tileType, px, py, x, y, extra);
      }
    }

    // Draw room archetype overlays
    for (const room of DUNGEON_ROOMS) {
      drawRoomOverlay(ctx, {
        archetype: room.purpose,
        theme: renderer.getTheme(),
        tileSize,
        roomOffsetX: 0,
        roomOffsetY: 0,
        roomWidth: DUNGEON_W,
        roomHeight: DUNGEON_H,
        bounds: room.bounds,
        doorPositions: room.doors,
        seed: 42,
      });

      // Room label
      const cx = ((room.bounds.x_min + room.bounds.x_max + 1) / 2) * tileSize;
      const cy = room.bounds.y_min * tileSize - 6;
      ctx.fillStyle = 'rgba(0,0,0,0.6)';
      const labelW = ctx.measureText(room.label).width + 12;
      ctx.fillRect(cx - labelW / 2, cy - 11, labelW, 16);
      ctx.fillStyle = '#daa520';
      ctx.font = 'bold 11px "Segoe UI", sans-serif';
      ctx.textAlign = 'center';
      ctx.fillText(room.label, cx, cy);
    }
  }, [themeId, tileSize]);

  const handleIsolatedClick = useCallback((e) => {
    const canvas = isolatedRef.current;
    if (!canvas) return;
    const rect = canvas.getBoundingClientRect();
    const mx = e.clientX - rect.left;
    const roomPxW = ROOM_W * tileSize;
    const gap = 16;
    const keys = Object.keys(ROOM_ARCHETYPES);

    if (mx < roomPxW) { setActiveArchetype(null); return; }
    for (let i = 0; i < keys.length; i++) {
      const colStart = (i + 1) * (roomPxW + gap);
      if (mx >= colStart && mx < colStart + roomPxW) {
        setActiveArchetype(keys[i]);
        return;
      }
    }
  }, [tileSize]);

  return (
    <div className="archetype-preview">
      <div className="preview-controls">
        <label>Zoom:</label>
        <input
          type="range"
          min="0.5"
          max="2"
          step="0.1"
          value={zoom}
          onChange={e => setZoom(parseFloat(e.target.value))}
        />
        <span>{Math.round(zoom * 100)}%</span>
        {activeArchetype && (
          <span className="hover-info">
            {ROOM_ARCHETYPES[activeArchetype]?.label}: {ROOM_ARCHETYPES[activeArchetype]?.description}
          </span>
        )}
      </div>
      <div className="preview-canvas-wrap archetype-scroll">
        <div className="archetype-sections">
          <div className="archetype-section">
            <h3 className="section-label">Side-by-Side Comparison — Click a room to see its description</h3>
            <canvas
              ref={isolatedRef}
              onClick={handleIsolatedClick}
              style={{ imageRendering: 'pixelated', cursor: 'pointer' }}
            />
          </div>
          <div className="archetype-section">
            <h3 className="section-label">Full Dungeon — All archetypes applied to labelled rooms</h3>
            <canvas
              ref={dungeonRef}
              style={{ imageRendering: 'pixelated' }}
            />
          </div>
        </div>
      </div>
    </div>
  );
}
