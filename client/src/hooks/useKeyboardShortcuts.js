/**
 * useKeyboardShortcuts.js — Keyboard shortcut effects for the Arena.
 * Extracted from Arena.jsx (P5 refactoring).
 *
 * Handles:
 *  - E: Context-sensitive interact (loot ground items, open chests, toggle doors)
 *  - I: Toggle inventory/character panel (dungeon only)
 *  - Tab / Shift+Tab: Cycle selectedTargetId through visible enemies (QoL-D)
 *  - Ctrl+A: Select all party members
 *  - F1: Target self, F2-F5: Target allied party member by index
 *  - Shift+F1: Take control of self, Shift+F2-F5: Take control of party member
 *  - Ctrl+1-4: Set stance for selected unit(s)
 *  - X: Clear queue + auto-target + action mode
 *  - Escape: Toggle in-game menu
 */
import { useEffect, useRef, useState } from 'react';

export default function useKeyboardShortcuts({
  matchStatus, partyMembers, players,
  selectedUnitIds, activeUnitId, playerId,
  isControllingAlly,
  visibleTiles, selectedTargetId,
  // Loot-system-overhaul: dungeon state for E-key interact
  groundItems, doorStates, chestStates, isDungeon,
  // Phase 12C: Portal extraction
  portal,
  // Phase 12-5: Stairs / floor transition
  tiles, tileLegend, stairsUnlocked,
  // Character panel toggle
  showInventory, onToggleInventory,
  // Phase 15 ESC menu
  showEscMenu, onToggleEscMenu,
  sendAction, dispatch,
}) {
  // ---------- Loot-System-Overhaul 3.3: ALT-to-Show-Labels state ----------
  const [altHeld, setAltHeld] = useState(false);

  // ---------- Minimap: M key toggle between normal/expanded (always visible) ----------
  const [minimapMode, setMinimapMode] = useState('normal'); // 'normal' | 'expanded'

  useEffect(() => {
    if (matchStatus !== 'in_progress') return;

    const handleMinimapKey = (e) => {
      if (e.key !== 'm' && e.key !== 'M') return;
      if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') return;
      if (e.ctrlKey || e.metaKey || e.altKey) return;

      e.preventDefault();
      setMinimapMode(prev => prev === 'normal' ? 'expanded' : 'normal');
    };

    window.addEventListener('keydown', handleMinimapKey);
    return () => window.removeEventListener('keydown', handleMinimapKey);
  }, [matchStatus]);

  // ---------- I key: Toggle Inventory/Character Panel (dungeon only) ----------
  // Only opens the panel when closed. When open, Inventory.jsx handles its own I-to-close.
  useEffect(() => {
    if (matchStatus !== 'in_progress') return;
    if (!isDungeon) return;
    if (showInventory) return; // Panel is open — Inventory.jsx owns the I key

    const handleInventoryKey = (e) => {
      if (e.key !== 'i' && e.key !== 'I') return;
      if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') return;
      if (e.ctrlKey || e.metaKey || e.altKey) return;

      e.preventDefault();
      onToggleInventory?.();
    };

    window.addEventListener('keydown', handleInventoryKey);
    return () => window.removeEventListener('keydown', handleInventoryKey);
  }, [matchStatus, isDungeon, showInventory, onToggleInventory]);

  // ---------- Phase 7B-2: Ctrl+A keyboard shortcut for Select All Party ----------
  // ---------- Phase 7C-3: F1-F4 select party member, Ctrl+1-4 stance quick-set ----------
  useEffect(() => {
    if (matchStatus !== 'in_progress') return;
    const hasParty = partyMembers && partyMembers.length > 0;
    if (!hasParty) return;

    const STANCES = ['follow', 'aggressive', 'defensive', 'hold'];

    const handleKeyDown = (e) => {
      // Ignore if typing in an input/textarea
      if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') return;

      if ((e.ctrlKey || e.metaKey) && e.key === 'a') {
        e.preventDefault();
        // Select all alive party members via server
        sendAction({ type: 'select_all_party' });
        dispatch({ type: 'SELECT_ALL_PARTY' });
        return;
      }

      // F1-F5: Target self/ally | Shift+F1-F5: Take control of self/ally
      const fKeyMatch = e.key.match(/^F(\d)$/);
      if (fKeyMatch && !e.ctrlKey && !e.metaKey && !e.altKey) {
        const fNum = parseInt(fKeyMatch[1], 10); // F1=1, F2=2, ...F5=5
        if (fNum < 1 || fNum > 5) return;

        if (e.shiftKey) {
          // --- Shift+F1-F5: Take control ---
          e.preventDefault();
          if (fNum === 1) {
            // Shift+F1: Return control to self (release any controlled ally)
            if (activeUnitId && activeUnitId !== playerId) {
              sendAction({ type: 'release_party_member', unit_id: activeUnitId });
            }
            dispatch({ type: 'SELECT_ACTIVE_UNIT', payload: null });
          } else {
            // Shift+F2-F5: Take control of party member [0]-[3]
            const idx = fNum - 2; // F2=0, F3=1, F4=2, F5=3
            if (idx >= 0 && idx < partyMembers.length) {
              const member = partyMembers[idx];
              const unit = players[member.unit_id];
              if (unit && unit.is_alive !== false) {
                sendAction({ type: 'select_party_member', unit_id: member.unit_id });
                dispatch({ type: 'SELECT_ACTIVE_UNIT', payload: member.unit_id });
              }
            }
          }
        } else {
          // --- F1-F5: Target self/ally (for heals, buffs, etc.) ---
          e.preventDefault();
          if (fNum === 1) {
            // F1: Target self
            dispatch({ type: 'SELECT_TARGET', payload: { targetId: playerId } });
          } else {
            // F2-F5: Target allied party member [0]-[3]
            const idx = fNum - 2; // F2=0, F3=1, F4=2, F5=3
            if (idx >= 0 && idx < partyMembers.length) {
              const member = partyMembers[idx];
              const unit = players[member.unit_id];
              if (unit && unit.is_alive !== false) {
                dispatch({ type: 'SELECT_TARGET', payload: { targetId: member.unit_id } });
              }
            }
          }
        }
        return;
      }

      // Phase 7C-3: Ctrl+1-4 — set stance for selected unit(s)
      if ((e.ctrlKey || e.metaKey) && e.key >= '1' && e.key <= '4') {
        e.preventDefault();
        const stanceIdx = parseInt(e.key, 10) - 1;
        const stance = STANCES[stanceIdx];
        if (!stance) return;

        // If multiple units selected, set all stances; otherwise set for active unit
        if (selectedUnitIds.length > 1) {
          sendAction({ type: 'set_all_stances', stance });
        } else if (activeUnitId && activeUnitId !== playerId) {
          sendAction({ type: 'set_stance', unit_id: activeUnitId, stance });
        }
        return;
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [matchStatus, partyMembers, sendAction, dispatch, players, selectedUnitIds, activeUnitId, playerId]);

  // ---------- Phase 15: Escape key — toggle in-game menu ----------
  useEffect(() => {
    if (matchStatus !== 'in_progress') return;

    const handleEscapeKey = (e) => {
      if (e.key !== 'Escape') return;
      if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') return;

      e.preventDefault();
      onToggleEscMenu?.();
    };

    window.addEventListener('keydown', handleEscapeKey);
    return () => window.removeEventListener('keydown', handleEscapeKey);
  }, [matchStatus, onToggleEscMenu]);

  // ---------- Phase 15: X key — clear queue + auto-target + action mode (moved from Escape) ----------
  useEffect(() => {
    if (matchStatus !== 'in_progress') return;

    const handleCancelKey = (e) => {
      if (e.key !== 'x' && e.key !== 'X') return;
      if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') return;
      if (e.ctrlKey || e.metaKey || e.altKey) return;
      // Don't cancel when ESC menu is open
      if (showEscMenu) return;

      e.preventDefault();

      // Clear action queue on server
      const clearMsg = { type: 'clear_queue' };
      if (isControllingAlly) clearMsg.unit_id = activeUnitId;
      sendAction(clearMsg);

      // Clear auto-target on server
      const clearAtMsg = { type: 'clear_auto_target' };
      if (isControllingAlly) clearAtMsg.unit_id = activeUnitId;
      sendAction(clearAtMsg);

      // Clear client state: action mode + auto-target + selected target
      dispatch({ type: 'SET_ACTION_MODE', payload: null });
      dispatch({ type: 'CLEAR_AUTO_TARGET' });
      dispatch({ type: 'CLEAR_SELECTED_TARGET' });
      dispatch({ type: 'QUEUE_CLEARED', payload: { unit_id: isControllingAlly ? activeUnitId : null } });
    };

    window.addEventListener('keydown', handleCancelKey);
    return () => window.removeEventListener('keydown', handleCancelKey);
  }, [matchStatus, sendAction, dispatch, isControllingAlly, activeUnitId, showEscMenu]);

  // ---------- Loot-System-Overhaul: E key — unified interact (loot, chest, door) ----------
  useEffect(() => {
    if (matchStatus !== 'in_progress') return;

    const handleInteractKey = (e) => {
      if (e.key !== 'e' && e.key !== 'E') return;
      if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') return;
      if (e.ctrlKey || e.metaKey || e.altKey) return;

      e.preventDefault();

      const effectiveId = activeUnitId || playerId;
      const activeUnit = players[effectiveId];
      if (!activeUnit || activeUnit.is_alive === false) return;
      // Phase 12C: Extracted heroes cannot interact — they've left the dungeon
      if (activeUnit.extracted) return;

      const px = activeUnit.position.x;
      const py = activeUnit.position.y;
      const playerKey = `${px},${py}`;

      // Helper: build action message with unit_id for ally control
      const buildMsg = (actionType, extra = {}) => {
        const msg = { type: 'action', action_type: actionType, ...extra };
        if (isControllingAlly) msg.unit_id = activeUnitId;
        return msg;
      };

      // --- Priority 0: Portal extraction (Phase 12C) ---
      // If standing on active portal tile, enter the portal
      if (portal && portal.active && px === portal.x && py === portal.y) {
        sendAction(buildMsg('interact', { target_id: 'enter_portal' }));
        dispatch({
          type: 'ADD_COMBAT_LOG',
          payload: { type: 'portal', message: 'Stepping through the portal...' },
        });
        return;
      }

      // --- Priority 0.5: Stairs interaction (Phase 12-5) ---
      // If standing on a stairs tile, descend to next floor
      if (isDungeon && tiles && tileLegend) {
        const tileRow = tiles[py];
        const tileChar = tileRow ? tileRow[px] : null;
        const tileType = tileChar ? (tileLegend[tileChar] || null) : null;
        if (tileType === 'stairs') {
          if (stairsUnlocked) {
            sendAction(buildMsg('interact', { target_id: 'enter_stairs' }));
            dispatch({
              type: 'ADD_COMBAT_LOG',
              payload: { type: 'system', message: 'Descending the stairs...' },
            });
            return;
          } else {
            dispatch({
              type: 'ADD_COMBAT_LOG',
              payload: { type: 'system', message: 'The stairs are sealed... defeat all enemies first!' },
            });
            return;
          }
        }
      }

      // --- Priority 1: Ground items on player's tile ---
      if (groundItems && groundItems[playerKey] && groundItems[playerKey].length > 0) {
        sendAction(buildMsg('loot', { target_x: px, target_y: py }));
        dispatch({
          type: 'ADD_COMBAT_LOG',
          payload: { type: 'system', message: 'Picking up items...' },
        });
        return;
      }

      // --- Priority 2: Adjacent unopened chest (8-directional) ---
      if (isDungeon && chestStates) {
        const cardinalOffsets = [[-1, 0], [1, 0], [0, -1], [0, 1], [-1, -1], [-1, 1], [1, -1], [1, 1]];
        for (const [dx, dy] of cardinalOffsets) {
          const cx = px + dx;
          const cy = py + dy;
          const chestKey = `${cx},${cy}`;
          if (chestStates[chestKey] === 'unopened') {
            sendAction(buildMsg('loot', { target_x: cx, target_y: cy }));
            dispatch({
              type: 'ADD_COMBAT_LOG',
              payload: { type: 'system', message: 'Opening chest...' },
            });
            return;
          }
        }
      }

      // --- Priority 3: Adjacent door (8-directional / Chebyshev) ---
      if (isDungeon && doorStates) {
        const allOffsets = [
          [-1, 0], [1, 0], [0, -1], [0, 1],
          [-1, -1], [-1, 1], [1, -1], [1, 1],
        ];
        for (const [dx, dy] of allOffsets) {
          const doorX = px + dx;
          const doorY = py + dy;
          const doorKey = `${doorX},${doorY}`;
          const doorState = doorStates[doorKey];
          if (doorState === 'closed') {
            sendAction(buildMsg('interact', { target_x: doorX, target_y: doorY }));
            dispatch({
              type: 'ADD_COMBAT_LOG',
              payload: { type: 'system', message: 'Opening door...' },
            });
            return;
          }
        }
      }

      // --- Nothing to interact with ---
      dispatch({
        type: 'ADD_COMBAT_LOG',
        payload: { type: 'system', message: 'Nothing to interact with here.' },
      });
    };

    window.addEventListener('keydown', handleInteractKey);
    return () => window.removeEventListener('keydown', handleInteractKey);
  }, [matchStatus, players, activeUnitId, playerId, isControllingAlly,
      groundItems, doorStates, chestStates, isDungeon, portal,
      tiles, tileLegend, stairsUnlocked,
      sendAction, dispatch]);

  // ---------- QoL-D: Tab-Targeting — cycle visible enemies nearest-first ----------
  const tabIndexRef = useRef(-1);
  // Reset tab index when selected target changes externally (e.g. left-click)
  useEffect(() => {
    if (!selectedTargetId) tabIndexRef.current = -1;
  }, [selectedTargetId]);

  useEffect(() => {
    if (matchStatus !== 'in_progress') return;

    const handleTabKey = (e) => {
      if (e.key !== 'Tab') return;
      if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') return;
      if (e.ctrlKey || e.metaKey || e.altKey) return;

      e.preventDefault();

      const effectiveUnitId = activeUnitId || playerId;
      const activeUnit = players[effectiveUnitId];
      if (!activeUnit || activeUnit.is_alive === false) return;
      const myTeam = activeUnit.team;
      if (!activeUnit.position) return;

      // Gather all visible, alive enemy units
      const enemies = [];
      for (const [id, unit] of Object.entries(players)) {
        if (!unit || unit.is_alive === false) continue;
        if (unit.team === myTeam) continue;
        if (!unit.position) continue;
        // FOV filter: if visibleTiles exists, only include enemies on visible tiles
        if (visibleTiles) {
          const tileKey = `${unit.position.x},${unit.position.y}`;
          if (!visibleTiles.has(tileKey)) continue;
        }
        const dx = unit.position.x - activeUnit.position.x;
        const dy = unit.position.y - activeUnit.position.y;
        const dist = Math.sqrt(dx * dx + dy * dy);
        enemies.push({ id, unit, dist });
      }

      if (enemies.length === 0) return;

      // Sort by distance (nearest first), then by id for stable ordering
      enemies.sort((a, b) => a.dist - b.dist || a.id.localeCompare(b.id));

      // Cycle direction: Shift+Tab = reverse
      const direction = e.shiftKey ? -1 : 1;

      // Find current index based on selectedTargetId
      const currentIdx = enemies.findIndex(e => e.id === selectedTargetId);
      let nextIdx;
      if (currentIdx === -1) {
        // No current target — start with nearest (Tab) or farthest (Shift+Tab)
        nextIdx = direction === 1 ? 0 : enemies.length - 1;
      } else {
        nextIdx = (currentIdx + direction + enemies.length) % enemies.length;
      }

      tabIndexRef.current = nextIdx;
      const newTarget = enemies[nextIdx];

      dispatch({ type: 'SELECT_TARGET', payload: { targetId: newTarget.id } });
    };

    window.addEventListener('keydown', handleTabKey);
    return () => window.removeEventListener('keydown', handleTabKey);
  }, [matchStatus, players, activeUnitId, playerId, visibleTiles, selectedTargetId, dispatch]);

  // ---------- Loot-System-Overhaul 3.3: ALT key held state for ground item labels ----------
  useEffect(() => {
    const handleKeyDown = (e) => {
      if (e.key === 'Alt') {
        e.preventDefault();
        setAltHeld(true);
      }
    };
    const handleKeyUp = (e) => {
      if (e.key === 'Alt') {
        setAltHeld(false);
      }
    };
    // Also release if window loses focus while ALT is held
    const handleBlur = () => setAltHeld(false);

    window.addEventListener('keydown', handleKeyDown);
    window.addEventListener('keyup', handleKeyUp);
    window.addEventListener('blur', handleBlur);
    return () => {
      window.removeEventListener('keydown', handleKeyDown);
      window.removeEventListener('keyup', handleKeyUp);
      window.removeEventListener('blur', handleBlur);
    };
  }, []);

  return { altHeld, minimapMode };
}
