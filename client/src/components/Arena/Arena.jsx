import React, { useEffect, useRef, useState, useCallback, useMemo } from 'react';
import { useGameState, useGameDispatch } from '../../context/GameStateContext';
import { TILE_SIZE, initCanvas, renderFrame, themeEngine } from '../../canvas/ArenaRenderer';
import { positionInterpolator } from '../../canvas/PositionInterpolator';
import { ParticleManager } from '../../canvas/particles/ParticleManager';
import { useAudioEvents } from '../../audio';
import useHighlights from '../../hooks/useHighlights';
import useCanvasInput from '../../hooks/useCanvasInput';
import useKeyboardShortcuts from '../../hooks/useKeyboardShortcuts';
import useWASDMovement from '../../hooks/useWASDMovement';
import HUD from '../HUD/HUD';
import HeaderBar from '../HeaderBar/HeaderBar';
import CombatLog from '../CombatLog/CombatLog';
import BottomBar from '../BottomBar/BottomBar';
import Inventory from '../Inventory/Inventory';
import PartyPanel from '../PartyPanel/PartyPanel';
import EnemyPanel from '../EnemyPanel/EnemyPanel';
import CombatMeter from '../CombatMeter/CombatMeter';
import MinimapPanel from '../MinimapPanel/MinimapPanel';
import EscapeMenu from '../EscapeMenu/EscapeMenu';
import LootNotification from '../HUD/LootNotification';
import EliteKillNotification from '../HUD/EliteKillNotification';
import { isNotableRarity } from '../../utils/itemUtils';

/**
 * Arena screen — the main game view with canvas grid, HUD, combat log, and actions.
 * WebSocket is owned by App — this component receives sendAction as a prop.
 * Manages the turn timer, canvas interactions, and action submission.
 */
export default function Arena({ sendAction, onMatchEnd, audioManager }) {
  const ctxRef = useRef(null);
  const canvasRef = useRef(null);
  const canvasAreaRef = useRef(null);
  const particleCanvasRef = useRef(null);
  const particleManagerRef = useRef(null);
  const gameState = useGameState();
  const dispatch = useGameDispatch();
  const [turnTimer, setTurnTimer] = useState(gameState.tickRate || 10);
  const [hoveredTile, setHoveredTile] = useState(null);
  const [showInventory, setShowInventory] = useState(false);
  const [showEscMenu, setShowEscMenu] = useState(false);
  const [containerSize, setContainerSize] = useState({ width: 0, height: 0 });
  // Phase 16G: Loot drop notifications (Rare+ items)
  const [lootNotifications, setLootNotifications] = useState([]);
  const lootNotifIdRef = useRef(0);
  // Phase 18F: Elite kill notifications (rare/super_unique deaths)
  const [eliteKillNotifications, setEliteKillNotifications] = useState([]);
  const eliteKillIdRef = useRef(0);

  const {
    players, playerId, matchId, matchStatus,
    gridWidth, gridHeight, obstacles, tickRate,
    actionMode, winner, winnerUsername,
    actionQueue, damageFloaters,
    visibleTiles, teamA, teamB, aiIds, matchType,
    // Roguelike exploration fog
    revealedTiles,
    // Dungeon state (4B-2)
    isDungeon, tiles, tileLegend, doorStates, chestStates,
    // Phase 4D: Loot
    groundItems,
    // Party control
    activeUnitId, partyMembers, partyQueues,
    // Phase 7B-2: Multi-selection
    selectedUnitIds,
    // Phase 6D: Skills
    classSkills, allClassSkills,
    // Phase 9E: Particle effects data
    lastTurnActions,
    // Phase 10C: Auto-target pursuit state
    autoTargetId,
    partyAutoTargets,
    // Phase 10G: Skill auto-target + selected target
    selectedTargetId,
    autoSkillId,
    partyAutoSkills,
    // Phase 12C: Portal scroll state
    portal,
    channeling,
    currentTurn,
    // Phase 26E: Totem entities
    totems,
    // Phase 23: Persistent AoE ground zones
    groundZones,
    // Theme system: server-assigned dungeon theme
    themeId,
  } = gameState;

  // Active unit: either the controlled party member or the player themselves
  const effectiveUnitId = activeUnitId || playerId;
  const isControllingAlly = activeUnitId && activeUnitId !== playerId;
  const activeUnit = players[effectiveUnitId];
  const myPlayer = players[playerId];
  const isAlive = activeUnit?.is_alive !== false;
  const myTeam = myPlayer?.team || 'a';

  // ---------- Reset Turn Timer on each turn result ----------
  const prevTurn = useRef(gameState.currentTurn);
  useEffect(() => {
    if (gameState.currentTurn !== prevTurn.current) {
      prevTurn.current = gameState.currentTurn;
      setTurnTimer(tickRate);
    }
  }, [gameState.currentTurn, tickRate]);

  // ---------- Phase 16G: Loot Drop Notifications ----------
  // Track groundItems changes and generate notifications for Rare+ items
  const prevGroundItemsRef = useRef(groundItems);
  useEffect(() => {
    const prev = prevGroundItemsRef.current;
    prevGroundItemsRef.current = groundItems;
    if (!groundItems || !isDungeon) return;

    // Find newly appeared items in groundItems
    for (const [key, items] of Object.entries(groundItems)) {
      if (!items) continue;
      const prevItems = prev?.[key] || [];
      for (const item of items) {
        // Check if this item existed in the previous groundItems for this tile
        const alreadyExisted = prevItems.some(pi =>
          (pi.instance_id && pi.instance_id === item.instance_id) ||
          (!pi.instance_id && pi.item_id === item.item_id && pi.name === item.name)
        );
        if (alreadyExisted) continue;
        // Check if it's a notable rarity
        if (isNotableRarity(item.rarity)) {
          lootNotifIdRef.current += 1;
          setLootNotifications(prev => [
            ...prev,
            { id: lootNotifIdRef.current, item, rarity: item.rarity, timestamp: Date.now() },
          ]);
        }
      }
    }
  }, [groundItems, isDungeon]);

  const handleDismissLootNotif = useCallback((id) => {
    setLootNotifications(prev => prev.filter(n => n.id !== id));
  }, []);

  // Phase 18F: Elite kill notifications from server
  const prevEliteKillsRef = useRef([]);
  useEffect(() => {
    const eliteKills = gameState.eliteKills || [];
    if (eliteKills.length === 0 || eliteKills === prevEliteKillsRef.current) {
      prevEliteKillsRef.current = eliteKills;
      return;
    }
    prevEliteKillsRef.current = eliteKills;
    for (const ek of eliteKills) {
      eliteKillIdRef.current += 1;
      setEliteKillNotifications(prev => [
        ...prev,
        {
          id: eliteKillIdRef.current,
          displayName: ek.display_name,
          monsterRarity: ek.monster_rarity || 'rare',
          timestamp: Date.now(),
        },
      ]);
    }
  }, [gameState.eliteKills]);

  const handleDismissEliteKill = useCallback((id) => {
    setEliteKillNotifications(prev => prev.filter(n => n.id !== id));
  }, []);

  // ---------- Turn Timer Countdown ----------
  useEffect(() => {
    if (matchStatus !== 'in_progress') return;

    const interval = setInterval(() => {
      setTurnTimer((prev) => Math.max(0, prev - 0.1));
    }, 100);

    return () => clearInterval(interval);
  }, [matchStatus]);

  // Reset timer when tickRate changes
  useEffect(() => {
    setTurnTimer(tickRate);
  }, [tickRate]);

  // ---------- Apply Server-Assigned Dungeon Theme ----------
  useEffect(() => {
    if (themeId && isDungeon) {
      themeEngine.setTheme(themeId, TILE_SIZE);
      console.log(`[Arena] Theme set from server: ${themeId}`);
    }
  }, [themeId, isDungeon]);

  // ---------- Measure Canvas Container (for adaptive viewport) ----------
  useEffect(() => {
    const el = canvasAreaRef.current;
    if (!el) return;
    const observer = new ResizeObserver((entries) => {
      const entry = entries[0];
      if (entry) {
        setContainerSize({
          width: entry.contentRect.width,
          height: entry.contentRect.height,
        });
      }
    });
    observer.observe(el);
    return () => observer.disconnect();
  }, []);

  // Compute canvas pixel dimensions — capped to container, snapped to tile boundaries.
  // Small maps that fit entirely use their natural size; larger maps get a viewport window.
  const canvasPixelW = useMemo(() => {
    const fullW = gridWidth * TILE_SIZE;
    if (containerSize.width <= 0 || containerSize.width >= fullW) return fullW;
    return Math.floor(containerSize.width / TILE_SIZE) * TILE_SIZE;
  }, [gridWidth, containerSize.width]);

  const canvasPixelH = useMemo(() => {
    const fullH = gridHeight * TILE_SIZE;
    if (containerSize.height <= 0 || containerSize.height >= fullH) return fullH;
    return Math.floor(containerSize.height / TILE_SIZE) * TILE_SIZE;
  }, [gridHeight, containerSize.height]);

  // ---------- Tile Highlights, Viewport, Queue Previews (extracted to useHighlights) ----------
  const {
    obstacleSet, doorSet, occupiedMap, friendlyUnitKeys,
    moveHighlights, attackHighlights, rangedHighlights,
    activeSkillDef, skillHighlights, interactHighlights,
    viewport, lootHighlightTile,
    currentQueue, queuePreviewTiles, hoverPreviews,
  } = useHighlights({
    players, playerId, activeUnit, effectiveUnitId, isAlive,
    gridWidth, gridHeight, obstacles,
    actionMode, myTeam,
    isDungeon, doorStates, chestStates, groundItems,
    activeUnitId,
    partyMembers, partyQueues, actionQueue, isControllingAlly,
    canvasPixelW, canvasPixelH,
    hoveredTile, matchStatus,
    selectedUnitIds,
    classSkills, allClassSkills,
    autoTargetId, partyAutoTargets,
    selectedTargetId, autoSkillId, partyAutoSkills,
  });

  // ---------- Damage Floater Cleanup ----------
  useEffect(() => {
    if (damageFloaters.length === 0) return;
    const timer = setInterval(() => {
      dispatch({ type: 'CLEAR_FLOATERS' });
    }, 200);
    return () => clearInterval(timer);
  }, [damageFloaters.length, dispatch]);

  // ---------- Keyboard Shortcuts (extracted to useKeyboardShortcuts) ----------
  const { altHeld, minimapMode } = useKeyboardShortcuts({
    matchStatus, partyMembers, players,
    selectedUnitIds, activeUnitId, playerId,
    isControllingAlly,
    visibleTiles, selectedTargetId,
    // Loot-system-overhaul: dungeon state for E-key interact
    groundItems, doorStates, chestStates, isDungeon,
    // Phase 12C: Portal extraction
    portal,
    // Phase 12-5: Stairs / floor transition
    tiles, tileLegend, stairsUnlocked: gameState.stairsUnlocked,
    // Character panel toggle
    showInventory,
    onToggleInventory: () => setShowInventory(prev => !prev),
    // Phase 15 ESC menu
    showEscMenu,
    onToggleEscMenu: () => setShowEscMenu(prev => !prev),
    sendAction, dispatch,
  });

  // ---------- WASD / Arrow-Key Movement ----------
  useWASDMovement({
    matchStatus, isAlive, activeUnit,
    effectiveUnitId, playerId, isControllingAlly,
    gridWidth, gridHeight,
    obstacleSet, occupiedMap, myTeam,
    sendAction, dispatch,
  });

  // ---------- Canvas Setup ----------
  useEffect(() => {
    const canvas = document.getElementById('arena-canvas');
    if (!canvas) return;
    canvas.width = canvasPixelW;
    canvas.height = canvasPixelH;
    ctxRef.current = canvas.getContext('2d');
    canvasRef.current = canvas;
  }, [canvasPixelW, canvasPixelH]);

  // ---------- Phase 9E: Particle System Setup ----------
  useEffect(() => {
    const pCanvas = particleCanvasRef.current;
    if (!pCanvas) return;

    const manager = new ParticleManager(pCanvas);
    particleManagerRef.current = manager;
    manager.resize(canvasPixelW, canvasPixelH);
    manager.init().then(() => manager.start());

    return () => {
      manager.destroy();
      particleManagerRef.current = null;
    };
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  // ---------- Phase 9E: Resize Particle Overlay ----------
  useEffect(() => {
    if (particleManagerRef.current) {
      particleManagerRef.current.resize(canvasPixelW, canvasPixelH);
    }
  }, [canvasPixelW, canvasPixelH]);

  // ---------- Phase 9E: Sync Particle Viewport ----------
  useEffect(() => {
    if (particleManagerRef.current) {
      particleManagerRef.current.setViewport(viewport.offsetX, viewport.offsetY);
    }
  }, [viewport]);

  // ---------- Phase 9E: Sync Player Positions for Tracked Effects ----------
  useEffect(() => {
    if (particleManagerRef.current) {
      particleManagerRef.current.setPlayers(players);
      // Phase 14E: Update CC status particle emitters (stun stars, slow frost)
      particleManagerRef.current.updateCCStatus(players, visibleTiles);
      // Persistent buff auras (war cry, armor, evasion, ward, prayer, taunt, bulwark)
      particleManagerRef.current.updateBuffStatus(players, visibleTiles);
      // Phase 18E (E5): Affix ambient particles (fire embers, frost crystals, etc.)
      particleManagerRef.current.updateAffixStatus(players, visibleTiles);
    }
  }, [players, visibleTiles]);

  // ---------- Phase 9E: Fire Particle Effects on Turn Result ----------
  useEffect(() => {
    if (!lastTurnActions || !particleManagerRef.current) return;
    const mgr = particleManagerRef.current;
    mgr.processActions(lastTurnActions.actions, players);
    mgr.processEnvironment(lastTurnActions.doorChanges, lastTurnActions.chestOpened);
  }, [lastTurnActions]); // eslint-disable-line react-hooks/exhaustive-deps

  // ---------- Phase 23: Update Ground Zone Particle Emitters ----------
  useEffect(() => {
    if (!particleManagerRef.current) return;
    particleManagerRef.current.updateGroundZones(groundZones || []);
  }, [groundZones]);

  // ---------- Phase 15D: Audio Effects on Turn Result ----------
  useAudioEvents(audioManager, lastTurnActions, players);

  // ---------- Position Interpolation: Feed new positions on each state update ----------
  useEffect(() => {
    positionInterpolator.update(players);
  }, [players]);

  // Clear interpolator on unmount (match end / leave)
  useEffect(() => {
    return () => positionInterpolator.clear();
  }, []);

  // ---------- Canvas Rendering (requestAnimationFrame loop for smooth interpolation) ----------
  // Store latest render params in a ref so the rAF loop always reads current values
  // without needing to restart the loop on every state change.
  const renderParamsRef = useRef(null);
  renderParamsRef.current = {
    gridWidth, gridHeight, obstacles, players,
    moveHighlights, attackHighlights, rangedHighlights, skillHighlights,
    hoveredTile, queuePreviewTiles, damageFloaters, visibleTiles,
    revealedTiles: isDungeon ? revealedTiles : null,
    playerId, myTeam, isDungeon, tiles, tileLegend, doorStates, chestStates,
    viewport, groundItems, lootHighlightTile, effectiveUnitId,
    selectedUnitIds, partyMembers: partyMembers || [],
    hoverPreviews, autoTargetId, partyAutoTargets: partyAutoTargets || {},
    selectedTargetId, autoSkillId, partyAutoSkills: partyAutoSkills || {},
    allClassSkills: allClassSkills || {}, classSkills: classSkills || [],
    altHeld, portal, channeling, currentTurn,
    // Phase 26E: Totems
    totems: totems || [],
    // Phase 23: Ground zones
    groundZones: groundZones || [],
  };

  // Dirty flag: set true whenever React state changes that affect rendering.
  // The rAF loop checks this + interpolator animation state to decide whether to redraw.
  const renderDirtyRef = useRef(true);
  useEffect(() => {
    renderDirtyRef.current = true;
  }, [players, obstacles, gridWidth, gridHeight, moveHighlights, attackHighlights,
      rangedHighlights, skillHighlights, hoveredTile, queuePreviewTiles, damageFloaters, visibleTiles,
      revealedTiles, selectedUnitIds,
      playerId, myTeam, isDungeon, tiles, tileLegend, doorStates, chestStates, viewport,
      groundItems, lootHighlightTile, effectiveUnitId, partyMembers, hoverPreviews,
      autoTargetId, partyAutoTargets, selectedTargetId,
      autoSkillId, partyAutoSkills, allClassSkills, classSkills, altHeld,
      portal, channeling, currentTurn, totems, groundZones]);

  useEffect(() => {
    let rafId = null;
    let running = true;

    function renderLoop() {
      if (!running) return;

      const needsRedraw = renderDirtyRef.current || positionInterpolator.isAnimating()
        || (renderParamsRef.current?.groundZones?.length > 0)
        || (renderParamsRef.current?.totems?.length > 0);

      if (needsRedraw && ctxRef.current) {
        renderDirtyRef.current = false;
        const p = renderParamsRef.current;
        const lerpPositions = positionInterpolator.getInterpolatedPositions();

        renderFrame(ctxRef.current, {
          gridWidth: p.gridWidth,
          gridHeight: p.gridHeight,
          obstacles: p.obstacles,
          players: p.players,
          moveHighlights: p.moveHighlights,
          attackHighlights: p.attackHighlights,
          rangedHighlights: p.rangedHighlights,
          skillHighlights: p.skillHighlights,
          selectedTile: p.hoveredTile,
          queuePreviewTiles: p.queuePreviewTiles,
          damageFloaters: p.damageFloaters,
          visibleTiles: p.visibleTiles,
          revealedTiles: p.revealedTiles,
          myPlayerId: p.playerId,
          myTeam: p.myTeam,
          isDungeon: p.isDungeon,
          tiles: p.tiles,
          tileLegend: p.tileLegend,
          doorStates: p.doorStates,
          chestStates: p.chestStates,
          viewportOffsetX: p.viewport.offsetX,
          viewportOffsetY: p.viewport.offsetY,
          groundItems: p.isDungeon ? p.groundItems : null,
          lootHighlightTile: p.lootHighlightTile,
          activeUnitId: p.effectiveUnitId,
          selectedUnitIds: p.selectedUnitIds,
          partyMembers: p.partyMembers,
          hoverPreviews: p.hoverPreviews,
          autoTargetId: p.autoTargetId,
          partyAutoTargets: p.partyAutoTargets,
          selectedTargetId: p.selectedTargetId,
          autoSkillId: p.autoSkillId,
          partyAutoSkills: p.partyAutoSkills,
          allClassSkills: p.allClassSkills,
          classSkills: p.classSkills,
          altHeld: p.altHeld,
          portal: p.portal,
          channeling: p.channeling,
          currentTurn: p.currentTurn,
          // Phase 26E: Totem entities
          totems: p.totems,
          // Phase 23: Ground zones
          groundZones: p.groundZones,
          // Pass interpolated positions for smooth movement
          interpolatedPositions: lerpPositions,
        });
      }

      rafId = requestAnimationFrame(renderLoop);
    }

    rafId = requestAnimationFrame(renderLoop);
    return () => {
      running = false;
      if (rafId) cancelAnimationFrame(rafId);
    };
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  // ---------- Canvas Input Handlers (extracted to useCanvasInput) ----------
  const {
    handleCanvasClick, handleContextMenu,
    handleCanvasMouseMove, handleCanvasMouseLeave,
  } = useCanvasInput({
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
  });

  // ---------- Action Handler (for BottomBar) ----------
  const handleAction = useCallback((action) => {
    sendAction(action);
  }, [sendAction]);

  // ---------- Leave Match ----------
  const handleLeave = () => {
    dispatch({ type: 'LEAVE_MATCH' });
    onMatchEnd();
  };

  // ---------- Match Stats ----------
  const matchStats = useMemo(() => {
    if (matchStatus !== 'finished') return null;
    // Compute stats from combat log
    const stats = {};
    for (const [pid, p] of Object.entries(players)) {
      stats[pid] = { username: p.username, kills: 0, damageDealt: 0, turnsSurvived: gameState.currentTurn };
    }
    // Parse combat log for damage/kill tracking
    for (const entry of gameState.combatLog) {
      if (entry.type === 'damage' || entry.type === 'kill') {
        // Messages follow: "Alice hit Bob for X damage"
        const match = entry.message?.match(/(.+) hit (.+) for (\d+) damage/);
        if (match) {
          const [, attackerName, , dmgStr] = match;
          const dmg = parseInt(dmgStr, 10);
          // Find attacker by username
          for (const [pid, s] of Object.entries(stats)) {
            if (s.username === attackerName) {
              s.damageDealt += dmg;
            }
          }
        }
        if (entry.type === 'kill') {
          const killMatch = entry.message?.match(/(.+) hit .+ for .+ — (.+) was killed/);
          if (killMatch) {
            const [, killerName] = killMatch;
            for (const [pid, s] of Object.entries(stats)) {
              if (s.username === killerName) {
                s.kills += 1;
              }
            }
          }
        }
      }
    }
    return Object.values(stats);
  }, [matchStatus, players, gameState.combatLog, gameState.currentTurn]);

  // ---------- Match End Overlay ----------
  const isFinished = matchStatus === 'finished';
  const isWinner = winner === playerId || winner === 'team_a' && myTeam === 'a' || winner === 'team_b' && myTeam === 'b' || winner === 'team_c' && myTeam === 'c' || winner === 'team_d' && myTeam === 'd' || winner === `team_${myTeam}`;

  return (
    <div className="arena">
      {/* 6E-2: Header zone — compact HeaderBar */}
      <div className="arena-header">
        <HeaderBar turnTimer={turnTimer} />
      </div>

      {/* Action bar — directly below header */}
      <div className="arena-bottom-bar">
        <BottomBar
          onAction={handleAction}
          onLeave={handleLeave}
        />
        {/* Combat Meter — drops below action bar when toggled */}
        <CombatMeter />
      </div>

      {/* Left panel — Combat Log */}
      <div className="arena-left-panel">
        <CombatLog />
      </div>

      {/* 6E-1: Canvas zone */}
      <div className="arena-canvas-area" ref={canvasAreaRef}>
        <div className="arena-grid" style={{ position: 'relative' }}>
          <canvas
            id="arena-canvas"
            width={canvasPixelW}
            height={canvasPixelH}
            onClick={handleCanvasClick}
            onContextMenu={handleContextMenu}
            onMouseMove={handleCanvasMouseMove}
            onMouseLeave={handleCanvasMouseLeave}
            style={{ cursor: (() => {
              if (actionMode) return 'crosshair';
              // Phase 10E-4: Crosshair cursor when hovering over an enemy (hints right-click auto-target)
              if (hoveredTile && isAlive) {
                const hoverKey = `${hoveredTile.x},${hoveredTile.y}`;
                const occupant = occupiedMap[hoverKey];
                if (occupant && occupant.team !== myTeam && occupant.pid !== effectiveUnitId) {
                  return 'crosshair';
                }
              }
              return 'default';
            })() }}
          />
          {/* Phase 9E: Particle effects overlay canvas */}
          <canvas
            ref={particleCanvasRef}
            width={canvasPixelW}
            height={canvasPixelH}
            style={{
              position: 'absolute',
              top: 0,
              left: 0,
              pointerEvents: 'none',
            }}
          />
          {/* Tile info tooltip */}
          {hoveredTile && (
            <div className="tile-tooltip">
              ({hoveredTile.x}, {hoveredTile.y})
              {occupiedMap[`${hoveredTile.x},${hoveredTile.y}`] && (
                <> — {occupiedMap[`${hoveredTile.x},${hoveredTile.y}`].username}
                  {' '}{occupiedMap[`${hoveredTile.x},${hoveredTile.y}`].hp}HP</>
              )}
              {obstacleSet.has(`${hoveredTile.x},${hoveredTile.y}`) && ' — Obstacle'}
              {doorStates[`${hoveredTile.x},${hoveredTile.y}`] === 'closed' && ' — Door (Closed)'}
              {doorStates[`${hoveredTile.x},${hoveredTile.y}`] === 'open' && ' — Door (Open)'}
              {chestStates[`${hoveredTile.x},${hoveredTile.y}`] === 'unopened' && ' — Chest'}
              {chestStates[`${hoveredTile.x},${hoveredTile.y}`] === 'opened' && ' — Chest (Opened)'}
              {groundItems && groundItems[`${hoveredTile.x},${hoveredTile.y}`] &&
                groundItems[`${hoveredTile.x},${hoveredTile.y}`].length > 0 && (
                <> — ✦ {groundItems[`${hoveredTile.x},${hoveredTile.y}`].length} item{groundItems[`${hoveredTile.x},${hoveredTile.y}`].length !== 1 ? 's' : ''} on ground</>
              )}
            </div>
          )}
          {/* Phase 12C: Portal prompt when standing on active portal tile */}
          {portal && portal.active && isAlive && activeUnit && !activeUnit.extracted &&
            activeUnit.position.x === portal.x && activeUnit.position.y === portal.y && (
            <div className="portal-prompt">
              ↯ Enter Portal — Press E to escape
            </div>
          )}
          {/* Loot prompt when player is standing on ground items */}
          {lootHighlightTile && isAlive && (
            <div className="loot-prompt">
              ✦ Items here! Press E to pick up
            </div>
          )}
        </div>
        {/* Minimap — overlays top-right of canvas area */}
        <MinimapPanel
          minimapMode={minimapMode}
          gridWidth={gridWidth}
          gridHeight={gridHeight}
          isDungeon={isDungeon}
          tiles={tiles}
          tileLegend={tileLegend}
          doorStates={doorStates}
          chestStates={chestStates}
          obstacles={obstacles}
          players={players}
          visibleTiles={visibleTiles}
          revealedTiles={isDungeon ? revealedTiles : null}
          myPlayerId={playerId}
          myTeam={myTeam}
          viewportOffsetX={viewport.offsetX}
          viewportOffsetY={viewport.offsetY}
          canvasPixelW={canvasPixelW}
          canvasPixelH={canvasPixelH}
          portal={portal}
          currentTurn={currentTurn}
          isPvpve={matchType === 'pvpve'}
          bossRoom={gameState.bossRoom || null}
        />
      </div>

      {/* Right panel — HUD + Party + Enemies */}
      <div className="arena-right-panel">
        <HUD turnTimer={turnTimer} />
        <PartyPanel sendAction={sendAction} />
        <EnemyPanel sendAction={sendAction} />
      </div>

      {/* 6E-5: Inventory Overlay (toggle from BottomBar bag icon, dungeon only) */}
      {isDungeon && showInventory && (
        <Inventory sendAction={sendAction} onClose={() => setShowInventory(false)} />
      )}

      {/* Phase 15: ESC Menu Overlay */}
      {showEscMenu && (
        <EscapeMenu
          onResume={() => setShowEscMenu(false)}
          onLeave={handleLeave}
        />
      )}

      {/* Phase 16G: Loot Drop Notifications */}
      {isDungeon && lootNotifications.length > 0 && (
        <LootNotification
          notifications={lootNotifications}
          onDismiss={handleDismissLootNotif}
        />
      )}

      {/* Phase 18F: Elite Kill Notifications */}
      {eliteKillNotifications.length > 0 && (
        <EliteKillNotification
          notifications={eliteKillNotifications}
          onDismiss={handleDismissEliteKill}
        />
      )}

      {/* Match End Overlay */}
      {isFinished && (
        <div className="match-end-overlay">
          <div className="match-end-box">
            <h2 className={isWinner ? 'victory-text' : 'defeat-text'}>
              {isWinner ? '🏆 Victory!' : '💀 Defeat'}
            </h2>
            <p className="end-message">
              {winnerUsername
                ? `${winnerUsername} wins the match!`
                : 'Match over!'}
            </p>
            {matchStats && (
              <div className="match-stats">
                <h3>Match Summary</h3>
                <table className="stats-table">
                  <thead>
                    <tr>
                      <th>Player</th>
                      <th>Kills</th>
                      <th>Damage</th>
                    </tr>
                  </thead>
                  <tbody>
                    {matchStats.map((s, i) => (
                      <tr key={i} className={s.username === winnerUsername ? 'winner-row' : ''}>
                        <td>{s.username}</td>
                        <td>{s.kills}</td>
                        <td>{s.damageDealt}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
            <button className="btn-return-lobby" onClick={handleLeave}>
              Return to Lobby
            </button>
          </div>
        </div>
      )}

    </div>
  );
}
