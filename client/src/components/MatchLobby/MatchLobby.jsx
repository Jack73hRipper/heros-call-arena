import React, { useState, useEffect, useCallback } from 'react';
import { useGameState, useGameDispatch } from '../../context/GameStateContext';
import { apiFetch } from '../../utils/serverUrl';
import BattleOrders from './BattleOrders';
import PartyAssembly from './PartyAssembly';
import DeployedForces from './DeployedForces';
import LobbyChatPanel from './LobbyChatPanel';

/**
 * MatchLobby — New unified lobby (Phase L1).
 *
 * Replaces the dual-entry flow (Enter Arena / Enter Dungeon) with a single
 * "Create Match" entry point. Three mode tabs: PvP · PvE · PvPvE.
 *
 * Layout: Header → Mode Tabs → [BattleOrders | Chat] → PartyAssembly → DeployedForces → Actions
 */

// Mode tab definitions — maps to internal match_type values
const MODE_TABS = [
  { id: 'pvp',   label: 'PvP',   icon: '⚔' },
  { id: 'pve',   label: 'PvE',   icon: '🏰' },
  { id: 'pvpve', label: 'PvPvE', icon: '💀' },
];

// Default config per mode — used to reset config when switching tabs
const MODE_DEFAULT_CONFIGS = {
  pvp: {
    match_type: 'pvp',
    map_id: 'arena_classic',
    ai_opponents: 0,
    ai_allies: 0,
    theme_id: null,
  },
  pve: {
    match_type: 'dungeon',
    map_id: 'procedural',
    ai_opponents: 0,
    ai_allies: 0,
    theme_id: null,
  },
  pvpve: {
    match_type: 'pvpve',
    map_id: 'procedural',
    ai_opponents: 0,
    ai_allies: 0,
    theme_id: null,
    pvpve_team_count: 2,
    pvpve_pve_density: 0.5,
    pvpve_boss_enabled: true,
    pvpve_grid_size: 8,
    pvpve_ai_team_count: 0,
    pvpve_ai_team_sizes: [],
  },
};

// Maps available per mode tab
const MODE_MAPS = {
  pvp: [
    { id: 'arena_classic', label: 'Arena Classic', description: 'Team vs Team combat. No PvE monsters. Pure player skill.' },
  ],
  pve: [
    { id: 'wave_arena', label: 'Wave Arena', description: '20×20 wave survival — escalating enemy waves' },
    { id: 'training_room', label: 'Training Room', description: '20×15 practice grounds — low stakes' },
    { id: 'wfc_dungeon', label: 'The Crypt', description: 'Procedural WFC dungeon — generated floors, rooms, bosses' },
  ],
  pvpve: [
    { id: 'the_crucible', label: 'The Crucible', description: 'Multiple teams clash while battling dungeon horrors.' },
  ],
};

// Internal match_type mapping — new mode tabs map to existing backend types
function getBackendMatchType(mode, mapId) {
  if (mode === 'pvp') return 'pvp';
  if (mode === 'pvpve') return 'pvpve';
  // PvE: map determines the backend type
  if (mapId === 'wave_arena') return 'solo_pve';
  if (mapId === 'training_room') return 'solo_pve';
  if (mapId === 'wfc_dungeon') return 'dungeon';
  return 'dungeon';
}

// Map ID to send to backend — procedural maps use 'procedural' virtual ID
function getBackendMapId(mode, mapId) {
  if (mode === 'pvp') return 'arena_classic';
  if (mode === 'pvpve') return 'procedural'; // The Crucible uses WFC generation
  if (mapId === 'wfc_dungeon') return 'procedural'; // The Crypt uses WFC generation
  return mapId;
}

export default function MatchLobby({ sendAction, onLeave, wsReady }) {
  const gameState = useGameState();
  const dispatch = useGameDispatch();
  const [isReady, setIsReady] = useState(false);
  const [leaving, setLeaving] = useState(false);

  const config = gameState.lobbyConfig || {};
  const lobbyMode = gameState.lobbyMode || 'pvp';
  const isHost = config.host_id === gameState.playerId;
  const lobbyPlayers = gameState.lobbyPlayers || {};
  const teamSlots = gameState.teamSlots || null;

  // Current player's team
  const myPlayer = lobbyPlayers[gameState.playerId];
  const playerTeam = myPlayer?.team || 'a';

  // Derive selected map from config
  const selectedMap = gameState.lobbySelectedMap || MODE_MAPS[lobbyMode]?.[0]?.id || 'arena_classic';

  // Count players
  const humanPlayers = Object.entries(lobbyPlayers).filter(([, p]) => p.unit_type !== 'ai');
  const aiPlayers = Object.entries(lobbyPlayers).filter(([, p]) => p.unit_type === 'ai');
  const humanCount = humanPlayers.length;
  const aiCount = aiPlayers.length;
  const totalCount = humanCount + aiCount;

  // Reset local isReady state when server un-readies us
  useEffect(() => {
    const myPlayer = lobbyPlayers[gameState.playerId];
    if (myPlayer && !myPlayer.is_ready && isReady) {
      setIsReady(false);
    }
  }, [lobbyPlayers, gameState.playerId, isReady]);

  // ── Mode Tab Switch (host only) ──
  // Sends full config reset to server — config resets to defaults when switching modes
  const handleModeChange = useCallback((newMode) => {
    if (!isHost || isReady) return;
    const defaultMap = MODE_MAPS[newMode]?.[0]?.id || 'arena_classic';
    const defaultConfig = { ...MODE_DEFAULT_CONFIGS[newMode] };
    // Override map_id with the backend-appropriate value
    defaultConfig.map_id = getBackendMapId(newMode, defaultMap);
    defaultConfig.match_type = getBackendMatchType(newMode, defaultMap);

    dispatch({ type: 'SET_LOBBY_MODE', payload: newMode });
    dispatch({ type: 'SET_LOBBY_SELECTED_MAP', payload: defaultMap });

    // Send full config reset to server — clears irrelevant fields from previous mode
    sendAction({
      type: 'lobby_config',
      config: defaultConfig,
    });
  }, [isHost, isReady, sendAction, dispatch]);

  // ── Map Change (host only, PvE tab) ──
  const handleMapChange = useCallback((mapId) => {
    if (!isHost || isReady) return;
    const backendType = getBackendMatchType(lobbyMode, mapId);
    const backendMap = getBackendMapId(lobbyMode, mapId);

    dispatch({ type: 'SET_LOBBY_SELECTED_MAP', payload: mapId });

    sendAction({
      type: 'lobby_config',
      config: {
        match_type: backendType,
        map_id: backendMap,
      },
    });
  }, [isHost, isReady, lobbyMode, sendAction, dispatch]);

  // ── Config Change (host only) ──
  const handleConfigChange = useCallback((updates) => {
    if (!isHost || isReady) return;
    sendAction({ type: 'lobby_config', config: updates });
  }, [isHost, isReady, sendAction]);

  // ── Team Change ──
  const handleTeamChange = useCallback((team) => {
    sendAction({ type: 'team_select', team });
  }, [sendAction]);

  // ── Ready / Start ──
  const handleReady = useCallback(() => {
    sendAction({ type: 'ready' });
    setIsReady(true);
  }, [sendAction]);

  // ── Leave / Retreat ──
  const handleLeave = useCallback(async () => {
    setLeaving(true);
    try {
      await apiFetch(`/api/lobby/leave/${gameState.matchId}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username: gameState.username }),
      });
    } catch (err) {
      console.error('[MatchLobby] Leave request failed:', err);
    }
    onLeave();
  }, [gameState.matchId, gameState.username, onLeave]);

  // ── Chat ──
  const handleSendChat = useCallback((message) => {
    sendAction({ type: 'lobby_chat', message });
  }, [sendAction]);

  // Current mode description
  const currentModeMap = MODE_MAPS[lobbyMode]?.find(m => m.id === selectedMap);
  const modeDescription = currentModeMap?.description || '';

  return (
    <div className="match-lobby">
      {/* ===== Header ===== */}
      <div className="match-lobby-header">
        <div className="match-lobby-title-block">
          <h2 className="match-lobby-title">War Room</h2>
          <p className="match-lobby-subtitle">Staging Ground</p>
        </div>
        <div className="match-lobby-meta">
          <span className="match-lobby-match-id">
            Match: <strong className="match-id-code">{gameState.matchId}</strong>
          </span>
          {isHost && <span className="match-lobby-host-badge">⚜ Commander</span>}
          <span className="match-lobby-headcount">
            {humanCount} human{humanCount !== 1 ? 's' : ''}
            {aiCount > 0 && `, ${aiCount} AI`}
            {' — '}{totalCount} total
          </span>
        </div>
      </div>

      {/* ===== Mode Tabs ===== */}
      <div className="match-lobby-mode-tabs">
        {MODE_TABS.map((tab) => (
          <button
            key={tab.id}
            className={`match-lobby-mode-tab ${lobbyMode === tab.id ? 'match-lobby-mode-tab--active' : ''}`}
            onClick={() => handleModeChange(tab.id)}
            disabled={!isHost || isReady}
          >
            <span className="mode-tab-icon">{tab.icon}</span>
            <span className="mode-tab-label">{tab.label}</span>
          </button>
        ))}
        {!isHost && (
          <span className="match-lobby-mode-label">
            Mode: <strong>{MODE_TABS.find(t => t.id === lobbyMode)?.label || lobbyMode}</strong>
          </span>
        )}
      </div>

      {/* Mode description banner */}
      {modeDescription && (
        <div className="match-lobby-mode-desc">
          {modeDescription}
        </div>
      )}

      {/* ===== Error Banner ===== */}
      {gameState.lobbyError && (
        <div className="lobby-error-banner">
          <span className="lobby-error-icon">⚠️</span>
          <span className="lobby-error-message">{gameState.lobbyError}</span>
          <button className="lobby-error-dismiss" onClick={() => dispatch({ type: 'SET_LOBBY_ERROR', payload: null })}>✕</button>
        </div>
      )}

      {/* ===== Two-Column: Battle Orders + Chat ===== */}
      <div className="match-lobby-columns">
        <div className="match-lobby-left grim-frame">
          <BattleOrders
            config={config}
            lobbyMode={lobbyMode}
            selectedMap={selectedMap}
            isHost={isHost}
            isReady={isReady}
            onMapChange={handleMapChange}
            onConfigChange={handleConfigChange}
            availableMaps={MODE_MAPS[lobbyMode] || []}
          />
        </div>
        <div className="match-lobby-right grim-frame">
          <LobbyChatPanel
            chat={gameState.lobbyChat || []}
            playerId={gameState.playerId}
            onSendChat={handleSendChat}
          />
        </div>
      </div>

      {/* ===== Party Assembly (Phase L2, L3) ===== */}
      <div className="match-lobby-section grim-frame">
        <PartyAssembly
          isReady={isReady}
          sendAction={sendAction}
          availableClasses={gameState.availableClasses || {}}
          teamSlots={teamSlots}
          playerTeam={playerTeam}
        />
      </div>

      {/* ===== Deployed Forces ===== */}
      <div className="match-lobby-section grim-frame">
        <DeployedForces
          lobbyPlayers={lobbyPlayers}
          playerId={gameState.playerId}
          config={config}
          isReady={isReady}
          onTeamChange={handleTeamChange}
          availableClasses={gameState.availableClasses || {}}
          teamSlots={teamSlots}
        />
      </div>

      {/* ===== Action Bar ===== */}
      <div className="match-lobby-actions">
        <button
          className="grim-btn grim-btn--sm grim-btn--crimson match-lobby-btn-leave"
          onClick={handleLeave}
          disabled={leaving}
        >
          {leaving ? 'Retreating...' : 'Retreat'}
        </button>
        {isHost ? (
          <button
            className="grim-btn grim-btn--lg grim-btn--ember grim-btn-pulse match-lobby-btn-start"
            onClick={handleReady}
            disabled={isReady}
          >
            {isReady ? '⚔ Awaiting Others...' : '⚔ Start Match'}
          </button>
        ) : (
          <button
            className={`grim-btn grim-btn--lg grim-btn--verdant grim-btn-pulse--verdant match-lobby-btn-ready ${isReady ? 'match-lobby-btn-ready--active' : ''}`}
            onClick={handleReady}
            disabled={isReady}
          >
            {isReady ? '⚔ Ready for Battle!' : '⚔ Ready Up'}
          </button>
        )}
      </div>
    </div>
  );
}
