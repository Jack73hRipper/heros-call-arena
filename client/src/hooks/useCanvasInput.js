/**
 * useCanvasInput.js — Canvas mouse/click handlers for the Arena grid.
 * Extracted from Arena.jsx (P5 refactoring).
 *
 * Returns handleCanvasClick, handleContextMenu, handleCanvasMouseMove,
 * handleCanvasMouseLeave.
 */
import { useCallback } from 'react';
import { pixelToTile } from '../canvas/ArenaRenderer';
import { generateSmartActions, computeGroupRightClick } from '../canvas/pathfinding';

export default function useCanvasInput({
  canvasRef, viewport,
  matchStatus, isAlive, actionMode,
  activeUnit, effectiveUnitId, playerId, myTeam,
  isControllingAlly, activeUnitId,
  moveHighlights, attackHighlights, rangedHighlights, interactHighlights, skillHighlights,
  obstacleSet, occupiedMap, doorSet,
  doorStates, chestStates, groundItems,
  gridWidth, gridHeight,
  currentQueue, friendlyUnitKeys,
  partyMembers, selectedUnitIds, players,
  autoTargetId,
  classSkills, allClassSkills,
  sendAction, dispatch,
  setHoveredTile,
}) {
  // ---------- Canvas Click Handler ----------
  const handleCanvasClick = useCallback((e) => {
    if (!canvasRef.current || matchStatus !== 'in_progress') return;
    const rect = canvasRef.current.getBoundingClientRect();
    const px = e.clientX - rect.left;
    const py = e.clientY - rect.top;
    const rawTile = pixelToTile(px, py);
    // Apply viewport offset to get world tile coords
    const tile = { x: rawTile.x + viewport.offsetX, y: rawTile.y + viewport.offsetY };

    // --- Party Member Click: Ctrl+Click = take control, Shift+Click = multi-select, Click = target ---
    if (!actionMode) {
      const key = `${tile.x},${tile.y}`;
      const occupant = occupiedMap[key];
      if (occupant && occupant.team === myTeam && occupant.pid !== playerId) {
        // Check if this is a controllable party member
        const isMember = partyMembers.some(m => m.unit_id === occupant.pid);
        if (isMember && occupant.is_alive !== false) {
          if (e.shiftKey) {
            // Shift-click: toggle multi-select (unchanged)
            const isCurrentlySelected = selectedUnitIds.includes(occupant.pid);
            if (isCurrentlySelected) {
              sendAction({ type: 'release_party_member', unit_id: occupant.pid });
            } else {
              sendAction({ type: 'select_party_member', unit_id: occupant.pid });
            }
            dispatch({ type: 'TOGGLE_UNIT_SELECTION', payload: occupant.pid });
          } else if (e.ctrlKey || e.metaKey) {
            // Ctrl+Click: take control of this party member
            for (const selId of selectedUnitIds) {
              if (selId !== playerId && selId !== occupant.pid) {
                sendAction({ type: 'release_party_member', unit_id: selId });
              }
            }
            sendAction({ type: 'select_party_member', unit_id: occupant.pid });
          } else {
            // Plain left-click: soft-select as target (for healing, etc.)
            dispatch({ type: 'SELECT_TARGET', payload: { targetId: occupant.pid } });
          }
          return;
        }
      }

      // Phase 7B-2: Clicking on the player themselves (self) — select self only
      if (occupant && occupant.pid === playerId) {
        // Return to self, deselect all party members
        for (const selId of selectedUnitIds) {
          if (selId !== playerId) {
            sendAction({ type: 'release_party_member', unit_id: selId });
          }
        }
        dispatch({ type: 'SELECT_ACTIVE_UNIT', payload: null });
        return;
      }

      // Phase 7B-2: Clicking empty space with no action mode — deselect all
      if (!occupant) {
        if (selectedUnitIds.length > 0) {
          for (const selId of selectedUnitIds) {
            if (selId !== playerId) {
              sendAction({ type: 'release_party_member', unit_id: selId });
            }
          }
          dispatch({ type: 'DESELECT_ALL_UNITS' });
        }
        // Phase 10G-5: Clear selected target when clicking empty space
        dispatch({ type: 'CLEAR_SELECTED_TARGET' });
        return;
      }

      // Phase 10G-5: Left-click on any other unit (enemy or non-party) → soft-select as target
      if (occupant && occupant.pid !== effectiveUnitId) {
        dispatch({ type: 'SELECT_TARGET', payload: { targetId: occupant.pid } });
        return;
      }
    }

    if (!isAlive) return;

    // Build action message — include unit_id when controlling an ally
    const buildMsg = (actionType, extra = {}) => {
      const msg = { type: 'action', action_type: actionType, ...extra };
      if (isControllingAlly) msg.unit_id = activeUnitId;
      return msg;
    };

    // Phase 10D-3 / Balance-pass: Only repositioning action modes clear
    // auto-target.  Combat action modes (attack, ranged_attack, skill_*)
    // preserve it so auto-attacks resume after the queued action resolves.
    const _REPOSITION_MODES = new Set(['move', 'interact']);
    if (autoTargetId && _REPOSITION_MODES.has(actionMode)) {
      dispatch({ type: 'CLEAR_AUTO_TARGET' });
    }

    if (actionMode === 'move') {
      // For queue model: compute valid moves from simulated future position
      // (after all queued moves), not just current position
      let simX = activeUnit.position.x;
      let simY = activeUnit.position.y;
      for (const qa of currentQueue) {
        if (qa.action_type === 'move' && qa.target_x != null) {
          simX = qa.target_x;
          simY = qa.target_y;
        }
      }

      // Check if clicked tile is adjacent to simulated position and valid
      const dx = Math.abs(tile.x - simX);
      const dy = Math.abs(tile.y - simY);
      const isAdjacent = dx <= 1 && dy <= 1 && !(dx === 0 && dy === 0);
      const key = `${tile.x},${tile.y}`;

      const isValidBasic = moveHighlights.some((t) => t.x === tile.x && t.y === tile.y);
      const isValidFromQueue = isAdjacent && !obstacleSet.has(key) &&
        tile.x >= 0 && tile.x < gridWidth && tile.y >= 0 && tile.y < gridHeight;

      if (isValidBasic || (currentQueue.length > 0 && isValidFromQueue)) {
        sendAction(buildMsg('move', { target_x: tile.x, target_y: tile.y }));
        // Don't reset action mode — allow queueing multiple moves
      }
    } else if (actionMode === 'attack') {
      // Check if clicked tile is a valid attack target
      const isValid = attackHighlights.some((t) => t.x === tile.x && t.y === tile.y);
      if (isValid) {
        const occupant = occupiedMap[`${tile.x},${tile.y}`];
        sendAction(buildMsg('attack', { target_x: tile.x, target_y: tile.y, target_id: occupant?.pid || null }));
        // Keep mode active for queueing multiple attacks
      }
    } else if (actionMode === 'ranged_attack') {
      // Check if clicked tile is a valid ranged target
      const isValid = rangedHighlights.some((t) => t.x === tile.x && t.y === tile.y);
      if (isValid) {
        const occupant = occupiedMap[`${tile.x},${tile.y}`];
        sendAction(buildMsg('ranged_attack', { target_x: tile.x, target_y: tile.y, target_id: occupant?.pid || null }));
      }
    } else if (actionMode === 'interact') {
      // Check if clicked tile is a valid interact target (adjacent closed door)
      const isValid = interactHighlights.some((t) => t.x === tile.x && t.y === tile.y);
      if (isValid) {
        sendAction(buildMsg('interact', { target_x: tile.x, target_y: tile.y }));
      }
    } else if (actionMode?.startsWith('skill_')) {
      // Phase 6D: Skill targeting click handler
      const skillId = actionMode.replace('skill_', '');
      const isValid = skillHighlights.some((t) => t.x === tile.x && t.y === tile.y);
      if (isValid) {
        const occupant = occupiedMap[`${tile.x},${tile.y}`];
        sendAction(buildMsg('skill', { skill_id: skillId, target_x: tile.x, target_y: tile.y, target_id: occupant?.pid || null }));
        // Keep mode active so player can queue multiple of the same skill if off cooldown
      }
    }
  }, [actionMode, moveHighlights, attackHighlights, rangedHighlights, interactHighlights, skillHighlights, isAlive, matchStatus, sendAction,
      activeUnit, currentQueue, obstacleSet, occupiedMap, gridWidth, gridHeight, viewport,
      partyMembers, activeUnitId, playerId, myTeam, isControllingAlly, dispatch, selectedUnitIds, autoTargetId]);

  // ---------- Smart Right-Click Handler ----------
  const handleContextMenu = useCallback((e) => {
    e.preventDefault(); // Prevent browser context menu
    if (!canvasRef.current || !isAlive || matchStatus !== 'in_progress') return;
    if (!activeUnit) return;

    const rect = canvasRef.current.getBoundingClientRect();
    const px = e.clientX - rect.left;
    const py = e.clientY - rect.top;
    const rawTile = pixelToTile(px, py);
    const tile = { x: rawTile.x + viewport.offsetX, y: rawTile.y + viewport.offsetY };

    // Bounds check
    if (tile.x < 0 || tile.x >= gridWidth || tile.y < 0 || tile.y >= gridHeight) return;

    // --- Phase 7B-3: Group Right-Click Movement ---
    // When multiple units are selected, compute group paths and send group_batch_actions
    if (selectedUnitIds.length > 1) {
      const groupResults = computeGroupRightClick(
        selectedUnitIds, playerId,
        tile.x, tile.y,
        gridWidth, gridHeight,
        obstacleSet, occupiedMap,
        doorStates, chestStates, groundItems,
        myTeam, players, 10, // MAX_QUEUE_SIZE
        friendlyUnitKeys,
        doorSet
      );

      if (!groupResults) {
        dispatch({
          type: 'ADD_COMBAT_LOG',
          payload: { type: 'system', message: 'Cannot reach that tile with group.' },
        });
        return;
      }

      // Build unit_actions payload for group_batch_actions WS message
      const unitActions = [];
      for (const { unitId, result } of groupResults) {
        if (result && result.actions && result.actions.length > 0) {
          unitActions.push({ unit_id: unitId, actions: result.actions });
        }
      }

      if (unitActions.length === 0) {
        dispatch({
          type: 'ADD_COMBAT_LOG',
          payload: { type: 'system', message: 'No valid paths for group movement.' },
        });
        return;
      }

      // Clear action mode (right-click replaces mode-based workflow)
      if (actionMode) {
        dispatch({ type: 'SET_ACTION_MODE', payload: null });
      }

      sendAction({ type: 'group_batch_actions', unit_actions: unitActions });

      // Phase 10D-5: Group right-click auto-target — if target is an enemy,
      // set auto-target for all selected units so they persistently pursue
      // Include each unit's class-specific auto-attack skill_id
      const targetKey = `${tile.x},${tile.y}`;
      const groupTargetOccupant = occupiedMap[targetKey];
      if (groupTargetOccupant && groupTargetOccupant.team !== myTeam && groupTargetOccupant.pid !== playerId) {
        for (const uid of selectedUnitIds) {
          const unitData = players[uid];
          const unitClassId = unitData?.class_id;
          const unitSkills = allClassSkills?.[unitClassId] || [];
          const autoSkill = unitSkills.find(s => s.is_auto_attack);
          const msg = { type: 'set_auto_target', target_id: groupTargetOccupant.pid, unit_id: uid };
          if (autoSkill) msg.skill_id = autoSkill.skill_id;
          sendAction(msg);
        }
      } else {
        // Non-attack group right-click: clear auto-target for all selected units
        for (const uid of selectedUnitIds) {
          sendAction({ type: 'clear_auto_target', unit_id: uid });
        }
      }

      // Log group movement for feedback
      dispatch({
        type: 'ADD_COMBAT_LOG',
        payload: { type: 'system', message: `Group move: ${unitActions.length} unit${unitActions.length !== 1 ? 's' : ''} pathing to (${tile.x}, ${tile.y})` },
      });
      return;
    }

    // --- Single unit right-click (existing behavior) ---

    // Check if clicking on a tile that's already in the queue preview → truncate to that point
    if (currentQueue && currentQueue.length > 0) {
      const queueIndex = currentQueue.findIndex(
        (a) => a.target_x === tile.x && a.target_y === tile.y
      );
      if (queueIndex >= 0) {
        // Truncate: keep actions 0..queueIndex, remove the rest
        const keepActions = currentQueue.slice(0, queueIndex + 1);
        const batchMsg = { type: 'batch_actions', actions: keepActions };
        if (isControllingAlly) batchMsg.unit_id = activeUnitId;
        sendAction(batchMsg);
        return;
      }
    }

    // Generate smart actions using A* pathfinding (from active unit position)
    // Phase 7A-2: Pass friendlyUnitKeys so A* doesn't treat allies as blockers
    // Determine auto-attack range for the active unit's class
    let autoAttackRange = null;
    if (activeUnit) {
      const unitClassId = activeUnit.class_id;
      const unitSkills = isControllingAlly
        ? (allClassSkills?.[unitClassId] || [])
        : (classSkills || []);
      const autoSkill = unitSkills.find(s => s.is_auto_attack);
      if (autoSkill && autoSkill.targeting === 'enemy_ranged') {
        // Ranged auto-attack: use the effective range
        autoAttackRange = autoSkill.range > 0 ? autoSkill.range : (activeUnit.ranged_range || 5);
      }
    }
    const result = generateSmartActions(
      activeUnit.position.x, activeUnit.position.y,
      tile.x, tile.y,
      gridWidth, gridHeight,
      obstacleSet, occupiedMap,
      doorStates, chestStates, groundItems,
      myTeam, effectiveUnitId, 10, // MAX_QUEUE_SIZE
      friendlyUnitKeys,
      null, // pendingMoves (single unit, no prediction needed)
      doorSet,
      autoAttackRange
    );

    if (!result || result.actions.length === 0) {
      // Show brief feedback for unreachable/invalid tile
      dispatch({
        type: 'ADD_COMBAT_LOG',
        payload: { type: 'system', message: 'Cannot reach that tile.' },
      });
      return;
    }

    // Clear action mode (right-click replaces mode-based workflow)
    if (actionMode) {
      dispatch({ type: 'SET_ACTION_MODE', payload: null });
    }

    // Send batch action to server (replaces current queue)
    const batchMsg = { type: 'batch_actions', actions: result.actions };
    if (isControllingAlly) batchMsg.unit_id = activeUnitId;
    sendAction(batchMsg);

    // Phase 10D-1: When right-clicking an enemy, also send set_auto_target
    // for persistent pursuit. The batch handles the initial approach; when the
    // queue runs dry, the server's auto-target takes over to keep chasing.
    // Include the class auto-attack skill_id so the server uses the proper
    // attack type (ranged for Ranger, melee for others).
    if (result.intent === 'attack') {
      const targetKey = `${tile.x},${tile.y}`;
      const targetInfo = occupiedMap[targetKey];
      if (targetInfo) {
        const unitId = isControllingAlly ? activeUnitId : effectiveUnitId;
        // Find auto-attack skill for this unit's class
        const unitClassId = activeUnit?.class_id;
        const unitSkills = isControllingAlly
          ? (allClassSkills?.[unitClassId] || [])
          : (classSkills || []);
        const autoAttackSkill = unitSkills.find(s => s.is_auto_attack);
        const autoTargetMsg = { type: 'set_auto_target', target_id: targetInfo.pid, unit_id: unitId };
        if (autoAttackSkill) {
          autoTargetMsg.skill_id = autoAttackSkill.skill_id;
        }
        sendAction(autoTargetMsg);
        // Phase 10G-5: Also set selected target to keep in sync
        dispatch({ type: 'SELECT_TARGET', payload: { targetId: targetInfo.pid } });
      }
    } else {
      // Phase 10D-2: Non-attack right-click (move, interact, loot) clears auto-target.
      // QoL-A: batch_actions no longer clears auto-target server-side, so this
      // explicit clear_auto_target message is the sole mechanism for non-attack
      // right-clicks to cancel pursuit.
      // Note: selectedTargetId is NOT cleared here — left-click soft-selection should
      // persist through movement so the player doesn't have to re-target after walking.
      const unitId = isControllingAlly ? activeUnitId : effectiveUnitId;
      sendAction({ type: 'clear_auto_target', unit_id: unitId });
      dispatch({ type: 'CLEAR_AUTO_TARGET' });
    }
  }, [isAlive, matchStatus, activeUnit, gridWidth, gridHeight, obstacleSet, occupiedMap,
      doorStates, chestStates, groundItems, myTeam, effectiveUnitId, currentQueue, actionMode,
      viewport, sendAction, dispatch, isControllingAlly, activeUnitId, friendlyUnitKeys,
      selectedUnitIds, playerId, players, doorSet, classSkills, allClassSkills]);

  // ---------- Canvas Hover Handler ----------
  // Phase 7E-1: Optimized to avoid creating new objects when tile hasn't changed,
  // preventing unnecessary re-renders and useMemo recomputations for hover previews.
  const handleCanvasMouseMove = useCallback((e) => {
    if (!canvasRef.current) return;
    const rect = canvasRef.current.getBoundingClientRect();
    const px = e.clientX - rect.left;
    const py = e.clientY - rect.top;
    const rawTile = pixelToTile(px, py);
    const tx = rawTile.x + viewport.offsetX;
    const ty = rawTile.y + viewport.offsetY;
    if (tx >= 0 && tx < gridWidth && ty >= 0 && ty < gridHeight) {
      setHoveredTile(prev => {
        if (prev && prev.x === tx && prev.y === ty) return prev; // Same tile — keep reference stable
        return { x: tx, y: ty };
      });
    } else {
      setHoveredTile(prev => prev === null ? prev : null);
    }
  }, [gridWidth, gridHeight, viewport]);

  const handleCanvasMouseLeave = useCallback(() => {
    setHoveredTile(null);
  }, []);

  return {
    handleCanvasClick,
    handleContextMenu,
    handleCanvasMouseMove,
    handleCanvasMouseLeave,
  };
}
