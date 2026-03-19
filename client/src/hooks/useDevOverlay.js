/**
 * useDevOverlay.js — Developer overlay for dungeon observation and debugging.
 *
 * Toggle with backtick (`) key during a match. Provides:
 *   - Clear fog of war (see entire map layout)
 *   - Free camera (detach viewport, pan with arrow keys)
 *   - Show all units (render enemies through fog)
 *   - Show grid coordinates on tiles
 *   - Show room boundaries & archetypes
 *   - Show spawn point markers
 *   - Unit inspector (click to inspect)
 *
 * When free camera is active, arrow keys are intercepted in the capture phase
 * so useWASDMovement (which listens in bubble phase) does not receive them.
 * WASD keys continue to work for character movement while free camera is on.
 */
import { useState, useEffect, useCallback, useRef } from 'react';
import { TILE_SIZE } from '../canvas/renderConstants';

export default function useDevOverlay({
  gridWidth, gridHeight, viewport, matchStatus,
  canvasPixelW, canvasPixelH, players, sendAction,
}) {
  const [devMode, setDevMode] = useState(false);
  const [fogDisabled, setFogDisabled] = useState(false);
  const [freeCam, setFreeCam] = useState(false);
  const [freeCamOffset, setFreeCamOffset] = useState({ x: 0, y: 0 });
  const [showGridCoords, setShowGridCoords] = useState(false);
  const [showAllUnits, setShowAllUnits] = useState(false);
  const [showRoomBounds, setShowRoomBounds] = useState(false);
  const [showSpawns, setShowSpawns] = useState(false);
  const [inspectMode, setInspectMode] = useState(false);
  const [inspectedUnit, setInspectedUnit] = useState(null);

  // Track current viewport for free cam initialization
  const viewportRef = useRef(viewport);
  viewportRef.current = viewport;

  // When toggling free cam on, snapshot current viewport position
  const prevFreeCam = useRef(false);
  useEffect(() => {
    if (freeCam && !prevFreeCam.current) {
      setFreeCamOffset({
        x: viewportRef.current.offsetX,
        y: viewportRef.current.offsetY,
      });
    }
    prevFreeCam.current = freeCam;
  }, [freeCam]);

  // Canvas tile dimensions for clamping
  const tilesVisibleX = Math.floor((canvasPixelW || 800) / TILE_SIZE);
  const tilesVisibleY = Math.floor((canvasPixelH || 600) / TILE_SIZE);

  // Free camera arrow key panning — capture phase intercepts before useWASDMovement
  useEffect(() => {
    if (!devMode || !freeCam || matchStatus !== 'in_progress') return;

    function handleKeyDown(e) {
      if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') return;

      const PAN_SPEED = 2;
      let handled = false;

      switch (e.code) {
        case 'ArrowUp':
          setFreeCamOffset(prev => ({
            ...prev,
            y: Math.max(0, prev.y - PAN_SPEED),
          }));
          handled = true;
          break;
        case 'ArrowDown':
          setFreeCamOffset(prev => ({
            ...prev,
            y: Math.min(Math.max(0, gridHeight - tilesVisibleY), prev.y + PAN_SPEED),
          }));
          handled = true;
          break;
        case 'ArrowLeft':
          setFreeCamOffset(prev => ({
            ...prev,
            x: Math.max(0, prev.x - PAN_SPEED),
          }));
          handled = true;
          break;
        case 'ArrowRight':
          setFreeCamOffset(prev => ({
            ...prev,
            x: Math.min(Math.max(0, gridWidth - tilesVisibleX), prev.x + PAN_SPEED),
          }));
          handled = true;
          break;
      }

      if (handled) {
        e.preventDefault();
        e.stopImmediatePropagation();
      }
    }

    window.addEventListener('keydown', handleKeyDown, { capture: true });
    return () => window.removeEventListener('keydown', handleKeyDown, { capture: true });
  }, [devMode, freeCam, matchStatus, gridWidth, gridHeight, tilesVisibleX, tilesVisibleY]);

  // Dev mode toggle — backtick key (always active during match)
  useEffect(() => {
    if (matchStatus !== 'in_progress') return;

    function handleKeyDown(e) {
      if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') return;
      if (e.code === 'Backquote') {
        e.preventDefault();
        setDevMode(prev => !prev);
      }
    }

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [matchStatus]);

  // Reset dev state when match ends
  useEffect(() => {
    if (matchStatus !== 'in_progress') {
      setDevMode(false);
      setFogDisabled(false);
      setFreeCam(false);
      setShowGridCoords(false);
      setShowAllUnits(false);
      setShowRoomBounds(false);
      setShowSpawns(false);
      setInspectMode(false);
      setInspectedUnit(null);
    }
  }, [matchStatus]);

  // Sync dev visibility state with server — when dev mode enables full visibility,
  // tell the server to skip FOV filtering so we receive all entity data
  useEffect(() => {
    if (!sendAction || matchStatus !== 'in_progress') return;
    const needsFullState = devMode && (fogDisabled || showAllUnits);
    sendAction({ type: 'dev_mode', enabled: needsFullState });
  }, [devMode, fogDisabled, showAllUnits, sendAction, matchStatus]);

  // Compute effective viewport
  const effectiveViewport = (devMode && freeCam)
    ? { offsetX: freeCamOffset.x, offsetY: freeCamOffset.y }
    : viewport;

  // Update inspected unit data when players change
  const inspectedRef = useRef(null);
  inspectedRef.current = inspectedUnit;
  useEffect(() => {
    if (inspectedRef.current && players) {
      const uid = inspectedRef.current.id;
      if (players[uid]) {
        setInspectedUnit({ id: uid, ...players[uid] });
      }
    }
  }, [players]);

  return {
    devMode,
    fogDisabled: devMode && fogDisabled,
    freeCam: devMode && freeCam,
    freeCamOffset,
    showGridCoords: devMode && showGridCoords,
    showAllUnits: devMode && showAllUnits,
    showRoomBounds: devMode && showRoomBounds,
    showSpawns: devMode && showSpawns,
    inspectMode: devMode && inspectMode,
    inspectedUnit,
    effectiveViewport,
    // Toggle actions
    toggleDev: useCallback(() => setDevMode(prev => !prev), []),
    toggleFog: useCallback(() => setFogDisabled(prev => !prev), []),
    toggleFreeCam: useCallback(() => setFreeCam(prev => !prev), []),
    toggleGridCoords: useCallback(() => setShowGridCoords(prev => !prev), []),
    toggleShowUnits: useCallback(() => setShowAllUnits(prev => !prev), []),
    toggleRoomBounds: useCallback(() => setShowRoomBounds(prev => !prev), []),
    toggleSpawns: useCallback(() => setShowSpawns(prev => !prev), []),
    toggleInspectMode: useCallback(() => setInspectMode(prev => !prev), []),
    inspectUnit: useCallback((unitId) => {
      if (unitId && players[unitId]) {
        setInspectedUnit({ id: unitId, ...players[unitId] });
      } else {
        setInspectedUnit(null);
      }
    }, [players]),
    resetCamera: useCallback(() => {
      setFreeCam(false);
      setFreeCamOffset({ x: 0, y: 0 });
    }, []),
  };
}
