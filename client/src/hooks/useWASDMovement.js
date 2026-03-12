/**
 * useWASDMovement.js — Roguelike-style WASD / Arrow-key movement.
 *
 * Hold two keys for diagonals (W+D = northeast, S+A = southwest, etc.).
 * Opposing keys cancel out (W+S = no vertical, A+D = no horizontal).
 *
 * Movement is "replace, not stack":
 *   - Only ONE move is ever queued from WASD at a time.
 *   - Changing direction replaces the queued move, so you can adjust freely
 *     before the tick resolves.
 *   - After a tick resolves (unit position changes), if keys are still held
 *     the next move in the current direction is auto-queued (continuous walk).
 *   - Releasing all keys leaves the last queued move intact.
 *
 * Co-exists with click-to-move — both feed into the same server action queue.
 */
import { useEffect, useRef, useCallback } from 'react';

// Which raw key codes map to which axis direction
const AXIS_KEYS = {
  // North (y-1)
  KeyW: 'north', ArrowUp: 'north',
  // South (y+1)
  KeyS: 'south', ArrowDown: 'south',
  // West (x-1)
  KeyA: 'west', ArrowLeft: 'west',
  // East (x+1)
  KeyD: 'east', ArrowRight: 'east',
};

/**
 * Combine held-axis flags into a [dx, dy] direction vector.
 * Opposing axes cancel. Returns null if no net direction.
 */
function resolveDirection(held) {
  let dx = 0;
  let dy = 0;
  if (held.north && !held.south) dy = -1;
  if (held.south && !held.north) dy = 1;
  if (held.west && !held.east) dx = -1;
  if (held.east && !held.west) dx = 1;
  if (dx === 0 && dy === 0) return null;
  return [dx, dy];
}

export default function useWASDMovement({
  matchStatus,
  isAlive,
  activeUnit,
  effectiveUnitId,
  playerId,
  isControllingAlly,
  gridWidth,
  gridHeight,
  obstacleSet,
  occupiedMap,
  myTeam,
  sendAction,
  dispatch,
}) {
  // Which directional axes are currently held
  const heldAxes = useRef({ north: false, south: false, west: false, east: false });

  // Whether we currently have a WASD move queued (to know when to replace vs first-queue)
  const wasdQueued = useRef(false);

  // Last direction we queued, so we can skip redundant sends
  const lastQueuedDir = useRef(null);

  // Store latest props in refs so the keydown/keyup closures always see current values
  const propsRef = useRef({});
  propsRef.current = {
    matchStatus, isAlive, activeUnit, effectiveUnitId, playerId,
    isControllingAlly, gridWidth, gridHeight, obstacleSet, occupiedMap,
    myTeam, sendAction,
  };

  /**
   * Send (or replace) the queued WASD move based on current held keys.
   * Uses batch_actions (clear + queue) so it atomically replaces any prior WASD move.
   */
  const syncMove = useCallback(() => {
    const {
      isAlive: alive, activeUnit: unit, effectiveUnitId: uid,
      isControllingAlly: ally, gridWidth: gw, gridHeight: gh,
      obstacleSet: obs, occupiedMap: occ, sendAction: send,
    } = propsRef.current;

    if (!alive || !unit?.position) return;

    const dir = resolveDirection(heldAxes.current);

    // No net direction — if we had something queued, clear it
    if (!dir) {
      if (wasdQueued.current) {
        // Don't clear — leave the last move queued so tap-and-release works.
        // Player can press X to clear if they change their mind.
        wasdQueued.current = false;
        lastQueuedDir.current = null;
      }
      return;
    }

    // If direction hasn't changed from what we already sent, skip
    const [dx, dy] = dir;
    if (lastQueuedDir.current &&
        lastQueuedDir.current[0] === dx && lastQueuedDir.current[1] === dy &&
        wasdQueued.current) {
      return;
    }

    const tx = unit.position.x + dx;
    const ty = unit.position.y + dy;

    // Bounds check
    if (tx < 0 || tx >= gw || ty < 0 || ty >= gh) return;

    // Obstacle check
    if (obs.has(`${tx},${ty}`)) return;

    // Occupied check — allow walking into same-team allies (server handles swap)
    const occupant = occ[`${tx},${ty}`];
    if (occupant && occupant.pid !== uid) {
      // Block WASD into enemies, but allow same-team for friendly swap
      if (!occupant.team || occupant.team !== propsRef.current.myTeam) return;
    }

    // Use batch_actions to atomically clear queue + queue this single move
    const msg = {
      type: 'batch_actions',
      actions: [{ action_type: 'move', target_x: tx, target_y: ty }],
    };
    if (ally) msg.unit_id = uid;
    send(msg);

    wasdQueued.current = true;
    lastQueuedDir.current = [dx, dy];
  }, []);

  // When the server position changes (tick resolved), auto-queue the next step
  // if keys are still held — gives continuous roguelike walking.
  useEffect(() => {
    if (!activeUnit?.position) return;
    // Only auto-continue if keys are still held
    const dir = resolveDirection(heldAxes.current);
    if (dir) {
      // Small delay to let the new position propagate to occupiedMap/obstacleSet
      const t = setTimeout(() => {
        wasdQueued.current = false;
        lastQueuedDir.current = null;
        syncMove();
      }, 30);
      return () => clearTimeout(t);
    } else {
      // Position updated but no keys held — reset tracking
      wasdQueued.current = false;
      lastQueuedDir.current = null;
    }
  }, [activeUnit?.position?.x, activeUnit?.position?.y, syncMove]);

  // Main keyboard listener
  useEffect(() => {
    if (matchStatus !== 'in_progress') return;

    function handleKeyDown(e) {
      if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') return;
      if (e.ctrlKey || e.metaKey || e.altKey) return;

      const axis = AXIS_KEYS[e.code];
      if (!axis) return;

      e.preventDefault();

      // If already held (browser auto-repeat), ignore
      if (heldAxes.current[axis]) return;

      heldAxes.current[axis] = true;
      syncMove();
    }

    function handleKeyUp(e) {
      const axis = AXIS_KEYS[e.code];
      if (!axis) return;

      heldAxes.current[axis] = false;
      // Re-evaluate: direction may have changed (e.g. released W while holding D)
      syncMove();
    }

    function handleBlur() {
      // Release all on window blur so keys don't stick
      heldAxes.current = { north: false, south: false, west: false, east: false };
      wasdQueued.current = false;
      lastQueuedDir.current = null;
    }

    window.addEventListener('keydown', handleKeyDown);
    window.addEventListener('keyup', handleKeyUp);
    window.addEventListener('blur', handleBlur);

    return () => {
      window.removeEventListener('keydown', handleKeyDown);
      window.removeEventListener('keyup', handleKeyUp);
      window.removeEventListener('blur', handleBlur);
    };
  }, [matchStatus, syncMove]);
}
