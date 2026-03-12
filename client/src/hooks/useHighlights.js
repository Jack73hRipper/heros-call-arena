/**
 * useHighlights.js — Tile highlight computations for the Arena canvas.
 * Extracted from Arena.jsx (P5 refactoring).
 *
 * Returns obstacleSet, doorSet, occupiedMap, friendlyUnitKeys, all highlight
 * arrays (move, attack, ranged, skill, interact), viewport, lootHighlightTile,
 * queuePreviewTiles, hoverPreviews, and activeSkillDef.
 */
import { useMemo } from 'react';
import { computeViewport } from '../canvas/ArenaRenderer';

export default function useHighlights({
  players, playerId, activeUnit, effectiveUnitId, isAlive,
  gridWidth, gridHeight, obstacles,
  actionMode, myTeam,
  isDungeon, doorStates, chestStates, groundItems,
  occupiedMapRaw,       // not used — we compute our own
  activeUnitId,
  partyMembers, partyQueues, actionQueue, isControllingAlly,
  canvasPixelW, canvasPixelH,
  hoveredTile, matchStatus,
  selectedUnitIds,
  classSkills, allClassSkills,
  autoTargetId, partyAutoTargets,
  selectedTargetId, autoSkillId, partyAutoSkills,
}) {
  // ---------- Compute Valid Tiles for Highlights ----------
  const obstacleSet = useMemo(() => {
    const set = new Set();
    for (const obs of obstacles) {
      set.add(`${obs.x},${obs.y}`);
    }
    // For dungeon maps, closed doors are also obstacles for movement validation
    // (you can't MOVE onto a closed door — must INTERACT first).
    // Phase 7D-1: Closed doors stay in obstacleSet for rendering/highlights,
    // but a separate doorSet is passed to A* so it can plan paths through them.
    if (isDungeon && doorStates) {
      for (const [key, state] of Object.entries(doorStates)) {
        if (state === 'closed') {
          set.add(key);
        }
      }
    }
    return set;
  }, [obstacles, isDungeon, doorStates]);

  // Phase 7D-1: Build a separate door tile set for A* pathfinding.
  // Closed doors are in obstacleSet (so move highlights don't show them as walkable),
  // but A* needs to be able to path *through* them at elevated cost. The doorSet
  // is passed to aStar() so it can remove these from blocked and apply door-crossing cost.
  const doorSet = useMemo(() => {
    if (!isDungeon || !doorStates) return null;
    const set = new Set();
    for (const [key, state] of Object.entries(doorStates)) {
      if (state === 'closed') {
        set.add(key);
      }
    }
    return set.size > 0 ? set : null;
  }, [isDungeon, doorStates]);

  const occupiedMap = useMemo(() => {
    // Map of "x,y" -> player info (includes team and unit_type)
    const map = {};
    for (const [pid, p] of Object.entries(players)) {
      if (p.is_alive !== false && !p.extracted) {
        map[`${p.position.x},${p.position.y}`] = { pid, ...p };
      }
    }
    return map;
  }, [players]);

  // Phase 7A-2: Build set of same-team unit positions to exclude from pathfinding
  const friendlyUnitKeys = useMemo(() => {
    const keys = new Set();
    for (const [key, info] of Object.entries(occupiedMap)) {
      if (info.team === myTeam && info.pid !== effectiveUnitId) {
        keys.add(key);
      }
    }
    return keys;
  }, [occupiedMap, myTeam, effectiveUnitId]);

  const moveHighlights = useMemo(() => {
    if (actionMode !== 'move' || !activeUnit || !isAlive) return [];
    const { x, y } = activeUnit.position;
    const tiles = [];
    for (let dx = -1; dx <= 1; dx++) {
      for (let dy = -1; dy <= 1; dy++) {
        if (dx === 0 && dy === 0) continue;
        const nx = x + dx;
        const ny = y + dy;
        if (nx < 0 || nx >= gridWidth || ny < 0 || ny >= gridHeight) continue;
        const key = `${nx},${ny}`;
        if (obstacleSet.has(key)) continue;
        // Phase 7A-2: Allow moving through same-team allies (server batch resolver handles it)
        const occupant = occupiedMap[key];
        if (occupant && !(occupant.team === myTeam && occupant.pid !== effectiveUnitId)) continue;
        tiles.push({ x: nx, y: ny });
      }
    }
    return tiles;
  }, [actionMode, activeUnit, isAlive, gridWidth, gridHeight, obstacleSet, occupiedMap, myTeam, effectiveUnitId]);

  const attackHighlights = useMemo(() => {
    if (actionMode !== 'attack' || !activeUnit || !isAlive) return [];
    const { x, y } = activeUnit.position;
    const tiles = [];
    for (let dx = -1; dx <= 1; dx++) {
      for (let dy = -1; dy <= 1; dy++) {
        if (dx === 0 && dy === 0) continue;
        const nx = x + dx;
        const ny = y + dy;
        const key = `${nx},${ny}`;
        // Only highlight tiles that have an enemy (not same team)
        const occupant = occupiedMap[key];
        if (occupant && occupant.pid !== effectiveUnitId && occupant.team !== myTeam) {
          tiles.push({ x: nx, y: ny });
        }
      }
    }
    return tiles;
  }, [actionMode, activeUnit, isAlive, effectiveUnitId, myTeam, occupiedMap]);

  // Ranged attack highlights — tiles within 5 range with LOS
  const rangedHighlights = useMemo(() => {
    if (actionMode !== 'ranged_attack' || !activeUnit || !isAlive) return [];
    const { x, y } = activeUnit.position;
    const range = 5;
    const tiles = [];

    for (let dx = -range; dx <= range; dx++) {
      for (let dy = -range; dy <= range; dy++) {
        if (dx === 0 && dy === 0) continue;
        if (dx * dx + dy * dy > range * range) continue;
        const nx = x + dx;
        const ny = y + dy;
        if (nx < 0 || nx >= gridWidth || ny < 0 || ny >= gridHeight) continue;
        const key = `${nx},${ny}`;
        // Only highlight tiles with enemies
        const occupant = occupiedMap[key];
        if (occupant && occupant.pid !== effectiveUnitId && occupant.team !== myTeam) {
          // Simple LOS check: make sure no obstacle is directly in the way
          // (full LOS is validated server-side, this is just visual hint)
          tiles.push({ x: nx, y: ny });
        }
      }
    }
    return tiles;
  }, [actionMode, activeUnit, isAlive, effectiveUnitId, myTeam, gridWidth, gridHeight, occupiedMap]);

  // ---------- Phase 6D: Skill targeting highlights ----------
  const activeSkillDef = useMemo(() => {
    if (!actionMode?.startsWith('skill_')) return null;
    const skillId = actionMode.replace('skill_', '');
    // Look up from classSkills or allClassSkills for controlled unit
    const isControlling = activeUnitId && activeUnitId !== playerId;
    const unitClassId = activeUnit?.class_id;
    const skills = isControlling
      ? (allClassSkills[unitClassId] || [])
      : (classSkills || []);
    return skills.find(s => s.skill_id === skillId) || null;
  }, [actionMode, classSkills, allClassSkills, activeUnit, activeUnitId, playerId]);

  const skillHighlights = useMemo(() => {
    if (!activeSkillDef || !activeUnit || !isAlive) return [];
    const { x, y } = activeUnit.position;
    const targeting = activeSkillDef.targeting;
    const range = activeSkillDef.range || 0;
    const tiles = [];

    if (targeting === 'self') {
      // Self-targeting: highlight own tile
      tiles.push({ x, y });
    } else if (targeting === 'ally_or_self') {
      // Highlight self + adjacent allies
      tiles.push({ x, y });
      for (let dx = -1; dx <= 1; dx++) {
        for (let dy = -1; dy <= 1; dy++) {
          if (dx === 0 && dy === 0) continue;
          const nx = x + dx;
          const ny = y + dy;
          if (nx < 0 || nx >= gridWidth || ny < 0 || ny >= gridHeight) continue;
          const key = `${nx},${ny}`;
          const occupant = occupiedMap[key];
          if (occupant && occupant.team === myTeam && occupant.is_alive !== false) {
            tiles.push({ x: nx, y: ny });
          }
        }
      }
    } else if (targeting === 'enemy_adjacent') {
      // Highlight adjacent enemies
      for (let dx = -1; dx <= 1; dx++) {
        for (let dy = -1; dy <= 1; dy++) {
          if (dx === 0 && dy === 0) continue;
          const nx = x + dx;
          const ny = y + dy;
          const key = `${nx},${ny}`;
          const occupant = occupiedMap[key];
          if (occupant && occupant.pid !== effectiveUnitId && occupant.team !== myTeam) {
            tiles.push({ x: nx, y: ny });
          }
        }
      }
    } else if (targeting === 'enemy_ranged') {
      // Highlight enemies within ranged range (use unit's ranged_range if skill range is 0)
      const effectiveRange = range > 0 ? range : (activeUnit.ranged_range || 5);
      for (let dx = -effectiveRange; dx <= effectiveRange; dx++) {
        for (let dy = -effectiveRange; dy <= effectiveRange; dy++) {
          if (dx === 0 && dy === 0) continue;
          if (dx * dx + dy * dy > effectiveRange * effectiveRange) continue;
          const nx = x + dx;
          const ny = y + dy;
          if (nx < 0 || nx >= gridWidth || ny < 0 || ny >= gridHeight) continue;
          const key = `${nx},${ny}`;
          const occupant = occupiedMap[key];
          if (occupant && occupant.pid !== effectiveUnitId && occupant.team !== myTeam) {
            tiles.push({ x: nx, y: ny });
          }
        }
      }
    } else if (targeting === 'ground_aoe') {
      // Ground AoE: highlight all tiles within range (walls excluded, enemies included)
      const effectiveRange = range > 0 ? range : 5;
      for (let dx = -effectiveRange; dx <= effectiveRange; dx++) {
        for (let dy = -effectiveRange; dy <= effectiveRange; dy++) {
          if (dx === 0 && dy === 0) continue;
          if (dx * dx + dy * dy > effectiveRange * effectiveRange) continue;
          const nx = x + dx;
          const ny = y + dy;
          if (nx < 0 || nx >= gridWidth || ny < 0 || ny >= gridHeight) continue;
          const key = `${nx},${ny}`;
          if (obstacleSet.has(key)) continue;
          tiles.push({ x: nx, y: ny });
        }
      }
    } else if (targeting === 'empty_tile') {
      // Highlight valid empty tiles within range with LOS
      const effectiveRange = range > 0 ? range : 3;
      for (let dx = -effectiveRange; dx <= effectiveRange; dx++) {
        for (let dy = -effectiveRange; dy <= effectiveRange; dy++) {
          if (dx === 0 && dy === 0) continue;
          if (dx * dx + dy * dy > effectiveRange * effectiveRange) continue;
          const nx = x + dx;
          const ny = y + dy;
          if (nx < 0 || nx >= gridWidth || ny < 0 || ny >= gridHeight) continue;
          const key = `${nx},${ny}`;
          if (obstacleSet.has(key)) continue;
          if (occupiedMap[key]) continue;
          tiles.push({ x: nx, y: ny });
        }
      }
    }
    return tiles;
  }, [activeSkillDef, activeUnit, isAlive, gridWidth, gridHeight, obstacleSet, occupiedMap, effectiveUnitId, myTeam]);

  // ---------- Dungeon: Interact highlights (all visible doors — queueable at any distance) ----------
  const interactHighlights = useMemo(() => {
    if (actionMode !== 'interact' || !activeUnit || !isAlive || !isDungeon) return [];
    const tiles = [];
    // Show all doors on the map as interact targets (server validates adjacency at execution)
    for (const [key, state] of Object.entries(doorStates)) {
      if (state === 'closed' || state === 'open') {
        const [dx, dy] = key.split(',').map(Number);
        tiles.push({ x: dx, y: dy });
      }
    }
    return tiles;
  }, [actionMode, activeUnit, isAlive, isDungeon, doorStates]);

  // ---------- Viewport / Camera (Phase 4B-2, universal for all map sizes) ----------
  const viewport = useMemo(() => {
    const myPlayer = players[playerId];
    // Center on active unit (controlled party member or self)
    const focusUnit = activeUnit || myPlayer;
    if (!focusUnit) return { offsetX: 0, offsetY: 0 };
    return computeViewport(focusUnit.position.x, focusUnit.position.y, gridWidth, gridHeight, canvasPixelW, canvasPixelH);
  }, [activeUnit, players, playerId, gridWidth, gridHeight, canvasPixelW, canvasPixelH]);

  // ---------- Loot Highlight (active unit standing on ground items) ----------
  const lootHighlightTile = useMemo(() => {
    if (!activeUnit || !isAlive || !groundItems) return null;
    const key = `${activeUnit.position.x},${activeUnit.position.y}`;
    if (groundItems[key] && groundItems[key].length > 0) {
      return { x: activeUnit.position.x, y: activeUnit.position.y };
    }
    return null;
  }, [activeUnit, isAlive, groundItems]);

  // ---------- Compute Queue Preview Tiles ----------
  const currentQueue = isControllingAlly ? (partyQueues[activeUnitId] || []) : actionQueue;
  const queuePreviewTiles = useMemo(() => {
    if (!currentQueue || currentQueue.length === 0 || !activeUnit || !isAlive) return [];

    const tiles = [];
    // Track simulated position for move chain
    let simX = activeUnit.position.x;
    let simY = activeUnit.position.y;

    for (const action of currentQueue) {
      if (action.action_type === 'move' && action.target_x != null && action.target_y != null) {
        simX = action.target_x;
        simY = action.target_y;
        tiles.push({ x: simX, y: simY, type: 'move' });
      } else if (action.action_type === 'attack' && action.target_x != null && action.target_y != null) {
        tiles.push({ x: action.target_x, y: action.target_y, type: 'attack' });
      } else if (action.action_type === 'ranged_attack' && action.target_x != null && action.target_y != null) {
        tiles.push({ x: action.target_x, y: action.target_y, type: 'ranged_attack' });
      } else if (action.action_type === 'wait') {
        tiles.push({ x: simX, y: simY, type: 'wait' });
      } else if (action.action_type === 'interact' && action.target_x != null && action.target_y != null) {
        tiles.push({ x: action.target_x, y: action.target_y, type: 'interact' });
      } else if (action.action_type === 'skill' && action.target_x != null && action.target_y != null) {
        tiles.push({ x: action.target_x, y: action.target_y, type: 'skill' });
      }
    }
    return tiles;
  }, [currentQueue, activeUnit, isAlive]);

  // ---------- Phase 7E-1: Hover Path Preview (disabled — paths now only shown on right-click move) ----------
  // The gold hovered-tile highlight is still active via selectedTile/drawSelectedTile.
  const hoverPreviews = null;

  return {
    obstacleSet,
    doorSet,
    occupiedMap,
    friendlyUnitKeys,
    moveHighlights,
    attackHighlights,
    rangedHighlights,
    activeSkillDef,
    skillHighlights,
    interactHighlights,
    viewport,
    lootHighlightTile,
    currentQueue,
    queuePreviewTiles,
    hoverPreviews,
  };
}
