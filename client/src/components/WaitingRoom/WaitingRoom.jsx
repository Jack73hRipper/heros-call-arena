import React, { useState, useRef, useEffect, useCallback } from 'react';
import { useGameState, useGameDispatch } from '../../context/GameStateContext';
import { apiFetch } from '../../utils/serverUrl';

// Fallback if server unreachable
const FALLBACK_MAPS = [
  { id: 'arena_classic', label: 'Arena Classic 15×15' },
];

// Virtual maps not backed by a JSON file on disk
const VIRTUAL_MAPS = [
  { id: 'procedural', name: 'Procedural Dungeon', width: 0, height: 0, map_type: 'dungeon', label: 'Procedural Dungeon (WFC)' },
];

const MATCH_TYPES = [
  { id: 'pvp',      label: 'PvP Only' },
  { id: 'solo_pve', label: 'Solo PvE' },
  { id: 'mixed',    label: 'Mixed (PvP + AI)' },
  { id: 'dungeon',  label: 'Dungeon' },
  { id: 'pvpve',    label: 'PVPVE' },
];

const PVPVE_GRID_SIZES = [
  { value: 6, label: 'Medium (6×6)' },
  { value: 8, label: 'Large (8×8)' },
  { value: 10, label: 'XL (10×10)' },
];

const PVPVE_DENSITY_LABELS = [
  { value: 0.3, label: 'Low' },
  { value: 0.5, label: 'Medium' },
  { value: 0.7, label: 'High' },
];

const TEAM_COLORS = {
  a: { label: 'Team A', color: '#4a8fd0' },
  b: { label: 'Team B', color: '#e04040' },
  c: { label: 'Team C', color: '#40c040' },
  d: { label: 'Team D', color: '#d4a017' },
};

// Team assignment order: player gets A, AI teams fill B, C, D
const _PVPVE_TEAM_KEYS_ORDER = ['a', 'b', 'c', 'd'];

const DUNGEON_THEMES = [
  { id: '',                    label: '🎲 Random Theme' },
  { id: 'bleeding_catacombs',  label: '🩸 Bleeding Catacombs' },
  { id: 'ashen_undercroft',    label: '🔥 Ashen Undercroft' },
  { id: 'drowned_sanctum',     label: '🌊 Drowned Sanctum' },
  { id: 'hollowed_cathedral',  label: '⛪ Hollowed Cathedral' },
  { id: 'iron_depths',         label: '⚙️ Iron Depths' },
  { id: 'forgotten_cellar',    label: '🪨 Forgotten Cellar' },
  { id: 'pale_ossuary',        label: '🦴 Pale Ossuary' },
  { id: 'silent_vault',        label: '🔇 Silent Vault' },
];

/**
 * WaitingRoom — War Room / Staging Ground (Phase 15, Chunk 5).
 *
 * Two-column layout: left panel (roster + config), right panel (chat).
 * Redesigned from narrow centered form to full-width war room.
 *
 * Features:
 * - Player list showing humans AND AI units as "unit cards" with team badges
 * - Host-only config controls styled as "battle orders"
 * - Chat window ("War Room Communications") with grim-frame styling
 * - Team selection dropdowns for all players
 * - Start Match (host) / Ready / Leave buttons with grim-btn system
 */
export default function WaitingRoom({ sendAction, onLeave, wsReady }) {
  const gameState = useGameState();
  const dispatch = useGameDispatch();
  const [isReady, setIsReady] = useState(false);
  const [leaving, setLeaving] = useState(false);
  const [chatInput, setChatInput] = useState('');
  const chatEndRef = useRef(null);
  const [maps, setMaps] = useState(FALLBACK_MAPS);

  // Fetch available maps from server on mount
  useEffect(() => {
    apiFetch('/api/maps/')
      .then(res => res.ok ? res.json() : Promise.reject('Failed'))
      .then(data => { if (data.length > 0) setMaps([...data, ...VIRTUAL_MAPS]); })
      .catch(() => console.warn('[WaitingRoom] Could not fetch maps, using fallback'));
  }, []);

  const config = gameState.lobbyConfig || {};
  const isHost = config.host_id === gameState.playerId;
  const availableClasses = gameState.availableClasses || {};

  // Auto-send hero_select when entering a dungeon waiting room with pre-selected heroes
  // Depends on wsReady so it re-fires once the WebSocket connection is established.
  // Retries once after a short delay if the server rejects (transient file-lock issue).
  const heroRetryRef = useRef(null);
  useEffect(() => {
    const heroIds = gameState.selectedHeroIds || [];
    console.log(`[WaitingRoom] hero_select useEffect: heroIds=${JSON.stringify(heroIds)} wsReady=${wsReady} matchId=${gameState.matchId} playerId=${gameState.playerId}`);
    if (heroIds.length > 0 && sendAction && wsReady) {
      console.log('[WaitingRoom] Sending hero_select:', heroIds);
      sendAction({ type: 'hero_select', hero_ids: heroIds });
    }
    return () => { if (heroRetryRef.current) clearTimeout(heroRetryRef.current); };
  }, [gameState.selectedHeroIds, sendAction, wsReady]);

  // If we receive a hero_select error, retry once after a brief delay
  useEffect(() => {
    if (
      gameState.lobbyError &&
      gameState.lobbyError.includes('Cannot select heroes') &&
      sendAction && wsReady
    ) {
      const heroIds = gameState.selectedHeroIds || [];
      if (heroIds.length > 0) {
        console.log('[WaitingRoom] hero_select failed, retrying in 500ms...');
        heroRetryRef.current = setTimeout(() => {
          sendAction({ type: 'hero_select', hero_ids: heroIds });
        }, 500);
      }
    }
    return () => { if (heroRetryRef.current) clearTimeout(heroRetryRef.current); };
  }, [gameState.lobbyError, gameState.selectedHeroIds, sendAction, wsReady]);

  // Reset local isReady state when server un-readies us (e.g. hero validation failure)
  const lobbyPlayers = gameState.lobbyPlayers || {};
  useEffect(() => {
    const myPlayer = lobbyPlayers[gameState.playerId];
    if (myPlayer && !myPlayer.is_ready && isReady) {
      setIsReady(false);
    }
  }, [lobbyPlayers, gameState.playerId, isReady]);

  // Auto-scroll chat to bottom on new messages
  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [gameState.lobbyChat]);

  const handleReady = () => {
    sendAction({ type: 'ready' });
    setIsReady(true);
  };

  const handleLeave = async () => {
    setLeaving(true);
    try {
      await apiFetch(`/api/lobby/leave/${gameState.matchId}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username: gameState.username }),
      });
    } catch (err) {
      console.error('[WaitingRoom] Leave request failed:', err);
    }
    onLeave();
  };

  const handleTeamChange = (team) => {
    sendAction({ type: 'team_select', team });
  };

  const handleClassChange = (classId) => {
    sendAction({ type: 'class_select', class_id: classId });
  };

  const handleSendChat = (e) => {
    e.preventDefault();
    const msg = chatInput.trim();
    if (!msg) return;
    sendAction({ type: 'lobby_chat', message: msg });
    setChatInput('');
  };

  const handleConfigChange = (updates) => {
    sendAction({ type: 'lobby_config', config: updates });
  };

  const players = lobbyPlayers;
  const humanPlayers = Object.entries(players).filter(([, p]) => p.unit_type !== 'ai');
  const aiPlayers = Object.entries(players).filter(([, p]) => p.unit_type === 'ai');
  const humanCount = humanPlayers.length;
  const aiCount = aiPlayers.length;
  const totalCount = humanCount + aiCount;

  const currentMatchType = config.match_type || 'pvp';
  const currentMap = config.map_id || 'arena_classic';

  return (
    <div className="war-room">
      {/* ===== War Room Header ===== */}
      <div className="war-room-header">
        <div className="war-room-title-block">
          <h2 className="war-room-title">War Room</h2>
          <p className="war-room-subtitle">Staging Ground</p>
        </div>
        <div className="war-room-meta">
          <span className="war-room-match-id">
            Match: <strong className="match-id-code">{gameState.matchId}</strong>
          </span>
          {isHost && <span className="war-room-host-badge">⚜ Commander</span>}
          <span className="war-room-headcount">
            {humanCount} human{humanCount !== 1 ? 's' : ''}
            {aiCount > 0 && `, ${aiCount} AI`}
            {' — '}{totalCount} total
            {humanCount < 2 && currentMatchType === 'pvp' && ' (need 2+ for PvP)'}
          </span>
        </div>
      </div>

      {(currentMap === 'procedural' || currentMatchType === 'pvpve') && (
        <div className="war-room-procedural-banner">
          <span className="procedural-badge">{currentMatchType === 'pvpve' ? '⚔ PVPVE Dungeon' : '⚡ Procedural Dungeon'}</span>
          <span className="procedural-hint">
            {currentMatchType === 'pvpve'
              ? 'Competitive dungeon — teams spawn in corners, fight PVE, and hunt each other'
              : 'Unique WFC-generated layout — dungeon will be created when match starts'}
          </span>
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

      {/* ===== Two-Column Layout ===== */}
      <div className="war-room-columns">

        {/* --- Left Panel: Config + Players --- */}
        <div className="war-room-left grim-frame">

          {/* Battle Orders (Config Panel) */}
          <div className="war-room-orders">
            <h3 className="grim-header grim-header--left grim-header--sm">
              Battle Orders {!isHost && <span className="config-readonly">(host controls)</span>}
            </h3>
            <div className="config-grid">
              {/* PVPVE always generates a procedural dungeon — hide map selector */}
              {currentMatchType !== 'pvpve' && (
                <div className="config-row">
                  <label>Map:</label>
                  {isHost ? (
                    <select
                      className="war-room-select"
                      value={currentMap}
                      onChange={(e) => handleConfigChange({ map_id: e.target.value })}
                      disabled={isReady}
                    >
                      {maps.map((m) => (
                        <option key={m.id} value={m.id}>{m.label}</option>
                      ))}
                    </select>
                  ) : (
                    <span className="config-value">{maps.find(m => m.id === currentMap)?.label || currentMap}</span>
                  )}
                </div>
              )}

              <div className="config-row">
                <label>Mode:</label>
                {isHost ? (
                  <div className="war-room-mode-btns">
                    {MATCH_TYPES.map((t) => (
                      <button
                        key={t.id}
                        className={`war-room-mode-btn ${currentMatchType === t.id ? 'war-room-mode-btn--active' : ''}`}
                        onClick={() => handleConfigChange({ match_type: t.id })}
                        disabled={isReady}
                      >
                        {t.label}
                      </button>
                    ))}
                  </div>
                ) : (
                  <span className="config-value">
                    {MATCH_TYPES.find(t => t.id === currentMatchType)?.label || currentMatchType}
                  </span>
                )}
              </div>

              {/* PVPVE-specific configuration */}
              {currentMatchType === 'pvpve' && (
                <>
                  <div className="config-row">
                    <label>Total Teams: {config.pvpve_team_count ?? 2}</label>
                    <span className="config-hint">How many competing teams in the dungeon (including yours)</span>
                    {isHost ? (
                      <input
                        type="range" min="2" max="4"
                        value={config.pvpve_team_count ?? 2}
                        onChange={(e) => handleConfigChange({ pvpve_team_count: Number(e.target.value) })}
                        disabled={isReady}
                      />
                    ) : (
                      <span className="config-value">{config.pvpve_team_count ?? 2} teams</span>
                    )}
                  </div>

                  <div className="config-row">
                    <label>Monster Density:</label>
                    <span className="config-hint">How many PVE enemies populate the dungeon rooms</span>
                    {isHost ? (
                      <select
                        className="war-room-select"
                        value={config.pvpve_pve_density ?? 0.5}
                        onChange={(e) => handleConfigChange({ pvpve_pve_density: Number(e.target.value) })}
                        disabled={isReady}
                      >
                        {PVPVE_DENSITY_LABELS.map((d) => (
                          <option key={d.value} value={d.value}>{d.label}</option>
                        ))}
                      </select>
                    ) : (
                      <span className="config-value">
                        {PVPVE_DENSITY_LABELS.find(d => d.value === (config.pvpve_pve_density ?? 0.5))?.label || 'Medium'}
                      </span>
                    )}
                  </div>

                  <div className="config-row">
                    <label>Grid Size:</label>
                    {isHost ? (
                      <select
                        className="war-room-select"
                        value={config.pvpve_grid_size ?? 8}
                        onChange={(e) => handleConfigChange({ pvpve_grid_size: Number(e.target.value) })}
                        disabled={isReady}
                      >
                        {PVPVE_GRID_SIZES.map((g) => (
                          <option key={g.value} value={g.value}>{g.label}</option>
                        ))}
                      </select>
                    ) : (
                      <span className="config-value">
                        {PVPVE_GRID_SIZES.find(g => g.value === (config.pvpve_grid_size ?? 8))?.label || 'Large (8×8)'}
                      </span>
                    )}
                  </div>

                  <div className="config-row">
                    <label>Boss Enabled:</label>
                    {isHost ? (
                      <button
                        className={`war-room-mode-btn ${(config.pvpve_boss_enabled !== false) ? 'war-room-mode-btn--active' : ''}`}
                        onClick={() => handleConfigChange({ pvpve_boss_enabled: !(config.pvpve_boss_enabled !== false) })}
                        disabled={isReady}
                      >
                        {(config.pvpve_boss_enabled !== false) ? '💀 Boss On' : '○ Boss Off'}
                      </button>
                    ) : (
                      <span className="config-value">{(config.pvpve_boss_enabled !== false) ? '💀 Boss On' : '○ Boss Off'}</span>
                    )}
                  </div>

                  {/* AI Teams — AI-controlled rival teams (fill empty team slots with bots) */}
                  <div className="config-row">
                    <label>AI Rival Teams: {config.pvpve_ai_team_count ?? 0}</label>
                    <span className="config-hint">Fill empty team slots with AI-controlled rival squads</span>
                    {isHost ? (
                      <input
                        type="range" min="0" max={Math.max(0, (config.pvpve_team_count ?? 2) - 1)}
                        value={config.pvpve_ai_team_count ?? 0}
                        onChange={(e) => handleConfigChange({ pvpve_ai_team_count: Number(e.target.value) })}
                        disabled={isReady}
                      />
                    ) : (
                      <span className="config-value">{config.pvpve_ai_team_count ?? 0}</span>
                    )}
                  </div>
                  {(config.pvpve_ai_team_count ?? 0) > 0 && (
                    <div className="config-row config-row--column">
                      <label>AI Team Sizes:</label>
                      <div className="ai-class-slots">
                        {Array.from({ length: config.pvpve_ai_team_count ?? 0 }, (_, teamIdx) => {
                          const teamKey = _PVPVE_TEAM_KEYS_ORDER[teamIdx + 1]; // skip team A (player's team)
                          const teamSizes = config.pvpve_ai_team_sizes || [];
                          const currentSize = teamSizes[teamIdx] ?? 3;
                          return (
                            <div key={`ai-team-${teamIdx}`} className="ai-class-slot">
                              <span className="ai-class-slot-label" style={{ color: TEAM_COLORS[teamKey]?.color || '#aaa' }}>
                                {TEAM_COLORS[teamKey]?.label || `Team ${teamKey?.toUpperCase()}`}
                              </span>
                              {isHost ? (
                                <input
                                  type="range" min="1" max="5"
                                  value={currentSize}
                                  onChange={(e) => {
                                    const updated = [...(config.pvpve_ai_team_sizes || [])];
                                    while (updated.length <= teamIdx) updated.push(3);
                                    updated[teamIdx] = Number(e.target.value);
                                    handleConfigChange({ pvpve_ai_team_sizes: updated });
                                  }}
                                  disabled={isReady}
                                  className="pvpve-team-size-slider"
                                />
                              ) : null}
                              <span className="config-value">{currentSize} units</span>
                            </div>
                          );
                        })}
                      </div>
                    </div>
                  )}
                </>
              )}

              {/* AI Opponents — hidden for PVP (no AI) and PVPVE (uses rival teams) */}
              {currentMatchType !== 'pvp' && currentMatchType !== 'pvpve' && (
                <>
                  <div className="config-row">
                    <label>AI Opponents: {config.ai_opponents ?? 0}</label>
                    {isHost ? (
                      <input
                        type="range" min="0" max="10"
                        value={config.ai_opponents ?? 0}
                        onChange={(e) => handleConfigChange({ ai_opponents: Number(e.target.value) })}
                        disabled={isReady}
                      />
                    ) : (
                      <span className="config-value">{config.ai_opponents ?? 0}</span>
                    )}
                  </div>

                  {/* AI Opponent Class Selection */}
                  {(config.ai_opponents ?? 0) > 0 && Object.keys(availableClasses).length > 0 && (
                    <div className="config-row config-row--column">
                      <label>Opponent Classes:</label>
                      <div className="ai-class-slots">
                        {Array.from({ length: config.ai_opponents ?? 0 }, (_, i) => {
                          const currentClass = (config.ai_opponent_classes || [])[i] || '';
                          return (
                            <div key={`opp-${i}`} className="ai-class-slot">
                              <span className="ai-class-slot-label">AI-{i + 1}</span>
                              {isHost ? (
                                <select
                                  className="war-room-select ai-class-select"
                                  value={currentClass}
                                  onChange={(e) => {
                                    const updated = [...(config.ai_opponent_classes || [])];
                                    // Ensure array is long enough
                                    while (updated.length <= i) updated.push('');
                                    updated[i] = e.target.value;
                                    handleConfigChange({ ai_opponent_classes: updated });
                                  }}
                                  disabled={isReady}
                                >
                                  <option value="">🎲 Random</option>
                                  {Object.entries(availableClasses).map(([cid, cls]) => (
                                    <option key={cid} value={cid}>{cls.name}</option>
                                  ))}
                                </select>
                              ) : (
                                <span className="config-value">
                                  {currentClass ? (availableClasses[currentClass]?.name || currentClass) : '🎲 Random'}
                                </span>
                              )}
                            </div>
                          );
                        })}
                      </div>
                    </div>
                  )}
                </>
              )}

              {/* AI Allies — available for all non-PVP modes (teammates on your team) */}
              {currentMatchType !== 'pvp' && (
                <>
                  <div className="config-row">
                    <label>AI Teammates: {config.ai_allies ?? 0}</label>
                    {currentMatchType === 'pvpve' && <span className="config-hint">Add AI allies to your own team</span>}
                    {isHost ? (
                      <input
                        type="range" min="0" max="10"
                        value={config.ai_allies ?? 0}
                        onChange={(e) => handleConfigChange({ ai_allies: Number(e.target.value) })}
                        disabled={isReady}
                      />
                    ) : (
                      <span className="config-value">{config.ai_allies ?? 0}</span>
                    )}
                  </div>

                  {/* AI Ally Class Selection */}
                  {(config.ai_allies ?? 0) > 0 && Object.keys(availableClasses).length > 0 && (
                    <div className="config-row config-row--column">
                      <label>Teammate Classes:</label>
                      <div className="ai-class-slots">
                        {Array.from({ length: config.ai_allies ?? 0 }, (_, i) => {
                          const currentClass = (config.ai_ally_classes || [])[i] || '';
                          return (
                            <div key={`ally-${i}`} className="ai-class-slot">
                              <span className="ai-class-slot-label">AI-{i + 1}</span>
                              {isHost ? (
                                <select
                                  className="war-room-select ai-class-select"
                                  value={currentClass}
                                  onChange={(e) => {
                                    const updated = [...(config.ai_ally_classes || [])];
                                    while (updated.length <= i) updated.push('');
                                    updated[i] = e.target.value;
                                    handleConfigChange({ ai_ally_classes: updated });
                                  }}
                                  disabled={isReady}
                                >
                                  <option value="">🎲 Random</option>
                                  {Object.entries(availableClasses).map(([cid, cls]) => (
                                    <option key={cid} value={cid}>{cls.name}</option>
                                  ))}
                                </select>
                              ) : (
                                <span className="config-value">
                                  {currentClass ? (availableClasses[currentClass]?.name || currentClass) : '🎲 Random'}
                                </span>
                              )}
                            </div>
                          );
                        })}
                      </div>
                    </div>
                  )}
                </>
              )}

              {/* Theme selector — visible for dungeon/pvpve match types */}
              {(currentMatchType === 'dungeon' || currentMatchType === 'solo_pve' || currentMatchType === 'mixed' || currentMatchType === 'pvpve') && (
                <div className="config-row">
                  <label>Dungeon Theme:</label>
                  {isHost ? (
                    <select
                      className="war-room-select theme-select"
                      value={config.theme_id || ''}
                      onChange={(e) => handleConfigChange({ theme_id: e.target.value || null })}
                      disabled={isReady}
                    >
                      {DUNGEON_THEMES.map((t) => (
                        <option key={t.id} value={t.id}>{t.label}</option>
                      ))}
                    </select>
                  ) : (
                    <span className="config-value">
                      {config.theme_id
                        ? (DUNGEON_THEMES.find(t => t.id === config.theme_id)?.label || config.theme_id)
                        : '🎲 Random Theme'
                      }
                    </span>
                  )}
                </div>
              )}
            </div>
          </div>

          <div className="grim-separator grim-separator--subtle">⬥</div>

          {/* Class Selection (Phase 4A) */}
          {Object.keys(availableClasses).length > 0 && (
            <>
              <div className="war-room-class-selection">
                <h3 className="grim-header grim-header--left grim-header--sm">Choose Your Class</h3>
                <div className="class-cards">
                  {Object.entries(availableClasses).map(([cid, cls]) => {
                    const myPlayer = players[gameState.playerId];
                    const isSelected = myPlayer?.class_id === cid;
                    return (
                      <div
                        key={cid}
                        className={`class-card ${isSelected ? 'class-card-selected' : ''}`}
                        style={{ borderColor: isSelected ? cls.color : '#333' }}
                        onClick={() => !isReady && handleClassChange(cid)}
                      >
                        <div className="class-card-header" style={{ color: cls.color }}>
                          <span className="class-card-shape" style={{ color: cls.color }}>
                            {cls.shape === 'square' ? '■' : cls.shape === 'triangle' ? '▲' : cls.shape === 'diamond' ? '◆' : cls.shape === 'star' ? '★' : cls.shape === 'hexagon' ? '⬡' : cls.shape === 'crescent' ? '☽' : cls.shape === 'shield' ? '🛡' : cls.shape === 'flask' ? '🧪' : cls.shape === 'coffin' ? '⚰️' : cls.shape === 'totem' ? '🪵' : '●'}
                          </span>
                          <strong>{cls.name}</strong>
                        </div>
                        <div className="class-card-role">{cls.role}</div>
                        <div className="class-card-stats">
                          <span>HP: {cls.base_hp}</span>
                          <span>Melee: {cls.base_melee_damage}</span>
                          <span>Ranged: {cls.base_ranged_damage}</span>
                          <span>Armor: {cls.base_armor}</span>
                          <span>Vision: {cls.base_vision_range}</span>
                          <span>Range: {cls.ranged_range}</span>
                        </div>
                        <div className="class-card-desc">{cls.description}</div>
                      </div>
                    );
                  })}
                </div>
              </div>
              <div className="grim-separator grim-separator--subtle">⬥</div>
            </>
          )}

          {/* Player Roster — Unit Cards */}
          <div className="war-room-roster">
            <h3 className="grim-header grim-header--left grim-header--sm">Deployed Units</h3>
            <div className="war-room-unit-list">
              {/* Human players */}
              {humanPlayers.map(([pid, player]) => {
                const cls = player.class_id && availableClasses[player.class_id];
                return (
                  <div
                    key={pid}
                    className={`war-unit-card ${player.is_ready ? 'war-unit-card--ready' : ''} ${pid === gameState.playerId ? 'war-unit-card--you' : ''}`}
                  >
                    <span className="war-unit-icon">
                      {pid === config.host_id ? '👑' : cls
                        ? (cls.shape === 'square' ? '■' : cls.shape === 'triangle' ? '▲' : cls.shape === 'diamond' ? '◆' : cls.shape === 'star' ? '★' : cls.shape === 'crescent' ? '☽' : cls.shape === 'shield' ? '🛡' : cls.shape === 'flask' ? '🧪' : cls.shape === 'coffin' ? '⚰️' : cls.shape === 'totem' ? '🪵' : '●')
                        : '⚔'}
                    </span>
                    <div className="war-unit-info">
                      <span className="war-unit-name">
                        {player.username}
                        {pid === gameState.playerId && <span className="war-unit-you">(you)</span>}
                      </span>
                      {cls && (
                        <span className="war-unit-class" style={{ color: cls.color }}>
                          {cls.name}
                        </span>
                      )}
                    </div>
                    <span className="war-unit-team">
                      {pid === gameState.playerId ? (
                        <select
                          className="team-select"
                          value={player.team || 'a'}
                          onChange={(e) => handleTeamChange(e.target.value)}
                          disabled={isReady}
                        >
                          <option value="a">Team A</option>
                          <option value="b">Team B</option>
                          <option value="c">Team C</option>
                          <option value="d">Team D</option>
                        </select>
                      ) : (
                        <span className={`team-badge team-${player.team || 'a'}`}>
                          Team {(player.team || 'a').toUpperCase()}
                        </span>
                      )}
                    </span>
                    <span className={`war-unit-status ${player.is_ready ? 'war-unit-status--ready' : ''}`}>
                      {player.is_ready ? '⚔ Ready' : '○ Waiting'}
                    </span>
                  </div>
                );
              })}

              {/* AI units */}
              {aiPlayers.map(([pid, player]) => {
                const cls = player.class_id && availableClasses[player.class_id];
                return (
                  <div key={pid} className="war-unit-card war-unit-card--ai war-unit-card--ready">
                    <span className="war-unit-icon">🤖</span>
                    <div className="war-unit-info">
                      <span className="war-unit-name">{player.username}</span>
                      <span className="war-unit-ai-role">
                        {cls && <span className="war-unit-class" style={{ color: cls.color }}>{cls.name}</span>}
                        <span className="war-unit-ai-type">{player.team === 'a' ? 'Ally' : player.team === 'pve' ? 'PVE' : 'Opponent'}</span>
                      </span>
                    </div>
                    <span className="war-unit-team">
                      <span className={`team-badge team-${player.team || 'b'}`}>
                        Team {(player.team || 'b').toUpperCase()}
                      </span>
                    </span>
                    <span className="war-unit-status war-unit-status--ready">⚔ Ready</span>
                  </div>
                );
              })}
            </div>
          </div>
        </div>

        {/* --- Right Panel: Chat --- */}
        <div className="war-room-right grim-frame">
          <h3 className="grim-header grim-header--left grim-header--sm">War Room Communications</h3>
          <div className="war-room-chat-messages">
            {(gameState.lobbyChat || []).length === 0 && (
              <p className="war-room-chat-placeholder">The war room is quiet... for now.</p>
            )}
            {(gameState.lobbyChat || []).map((msg, i) => (
              <div key={i} className={`chat-msg ${msg.sender_id === gameState.playerId ? 'chat-msg-me' : ''}`}>
                <span className="chat-sender">{msg.sender}:</span>
                <span className="chat-text">{msg.message}</span>
              </div>
            ))}
            <div ref={chatEndRef} />
          </div>
          <form className="war-room-chat-form" onSubmit={handleSendChat}>
            <input
              type="text"
              className="war-room-chat-input"
              placeholder="Issue orders..."
              value={chatInput}
              onChange={(e) => setChatInput(e.target.value)}
              maxLength={500}
            />
            <button type="submit" className="grim-btn grim-btn--sm grim-btn--ember" disabled={!chatInput.trim()}>
              Send
            </button>
          </form>
        </div>
      </div>

      {/* ===== Action Buttons — Full-width bottom bar ===== */}
      <div className="war-room-actions">
        {isHost && (
          <button
            className="grim-btn grim-btn--lg grim-btn--ember grim-btn-pulse war-room-btn-start"
            onClick={handleReady}
            disabled={isReady}
          >
            {isReady ? '⚔ Awaiting Others...' : '⚔ Start Match'}
          </button>
        )}
        {!isHost && (
          <button
            className={`grim-btn grim-btn--lg grim-btn--verdant grim-btn-pulse--verdant war-room-btn-ready ${isReady ? 'war-room-btn-ready--active' : ''}`}
            onClick={handleReady}
            disabled={isReady}
          >
            {isReady ? '⚔ Ready for Battle!' : '⚔ Ready Up'}
          </button>
        )}
        <button
          className="grim-btn grim-btn--sm grim-btn--crimson war-room-btn-leave"
          onClick={handleLeave}
          disabled={leaving}
        >
          {leaving ? 'Retreating...' : 'Retreat'}
        </button>
      </div>
    </div>
  );
}
