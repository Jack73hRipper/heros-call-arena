import React, { useState, useCallback, useEffect, useRef } from 'react';
import { GameStateProvider, useGameState, useGameDispatch } from './context/GameStateContext';
import { fetchWithRetry } from './utils/fetchWithRetry';
import { apiFetch } from './utils/serverUrl';
import useWebSocket from './hooks/useWebSocket';
import { useAudio, useAmbientAudio, AudioProvider } from './audio';
import VolumeSettings from './components/VolumeSettings/VolumeSettings';
import Lobby from './components/Lobby/Lobby';
import WaitingRoom from './components/WaitingRoom/WaitingRoom';
import Arena from './components/Arena/Arena';
import TownHub from './components/TownHub/TownHub';
import PostMatchScreen from './components/PostMatch/PostMatchScreen';

/**
 * AppInner — lives inside GameStateProvider so it can access game state.
 * Owns the single WebSocket connection that persists across WaitingRoom → Arena.
 *
 * Screen flow (Phase 4E-3):
 *   lobby → town → (arena: create/join via lobby flow)
 *                → (dungeon: create with hero_id via town flow)
 *   arena → postmatch → town
 *   dungeon → postmatch → town
 */
function AppInner() {
  const [screen, setScreenRaw] = useState('lobby'); // 'lobby' | 'waiting' | 'arena' | 'town' | 'postmatch'
  const screenKeyRef = useRef(0); // Increments on screen change to trigger re-mount & CSS enter animation
  const gameState = useGameState();
  const dispatch = useGameDispatch();

  // ── Audio System (Phase 15D) ──
  const {
    audioManager, resumeAudio, playUI,
    setMasterVolume, setSfxVolume, setAmbientVolume, setUIVolume,
    setMusicVolume, toggleMute, toggleMusic, nextTrack, prevTrack,
    getMusicState, onMusicChange, getSettings,
  } = useAudio();
  useAmbientAudio(audioManager, screen, gameState.isDungeon);

  const volumeControls = {
    setMasterVolume, setSfxVolume, setAmbientVolume, setUIVolume,
    setMusicVolume, toggleMute, toggleMusic, nextTrack, prevTrack,
    getMusicState, onMusicChange, getSettings,
  };

  // Wrap setScreen to increment key for CSS enter animations + audio events
  const setScreen = useCallback((next) => {
    screenKeyRef.current += 1;
    setScreenRaw(next);
    // Fire audio events on screen transitions
    if (next === 'arena' && audioManager.current) {
      audioManager.current.processEvent('match_start');
    }
    if (next === 'postmatch' && audioManager.current) {
      audioManager.current.processEvent('match_end');
    }
  }, [audioManager]);

  // Fetch available classes on mount (retries if backend is still starting)
  useEffect(() => {
    fetchWithRetry('/api/lobby/classes')
      .then(res => res.json())
      .then(data => {
        dispatch({ type: 'SET_AVAILABLE_CLASSES', payload: data.classes });
      })
      .catch(err => console.error('[App] Failed to fetch classes:', err));
  }, [dispatch]);

  // Unified WebSocket message handler — routes to correct dispatcher based on screen/type
  const handleMessage = useCallback((data) => {
    switch (data.type) {
      case 'player_joined':
        dispatch({ type: 'PLAYER_JOINED', payload: data });
        break;
      case 'player_ready':
        dispatch({ type: 'PLAYER_READY', payload: data });
        break;
      case 'match_start':
        dispatch({ type: 'MATCH_START', payload: data });
        setScreen('arena');
        break;
      case 'turn_result':
        dispatch({ type: 'TURN_RESULT', payload: data });
        // Feed combat stats reducer with structured action data
        dispatch({
          type: 'COMBAT_STATS_UPDATE',
          payload: {
            actions: data.actions || [],
            players: data.players || {},
            turnNumber: data.turn_number || 0,
            deaths: data.deaths || [],
            items_used: data.items_used || [],
            items_picked_up: data.items_picked_up || [],
          },
        });
        // Process hero deaths for permadeath notifications
        if (data.hero_deaths && data.hero_deaths.length > 0) {
          for (const hd of data.hero_deaths) {
            dispatch({ type: 'HERO_DIED', payload: hd });
          }
        }
        // Phase 15D: Portal audio events from turn_result
        if (data.portal_spawned && audioManager.current) {
          audioManager.current.processEvent('portal_open');
        }
        if (data.channeling && audioManager.current) {
          audioManager.current.processEvent('portal_channel');
        }
        break;
      case 'match_end':
        dispatch({ type: 'MATCH_END', payload: data });
        // Build post-match summary and transition to postmatch screen
        dispatch({
          type: 'SET_POST_MATCH_SUMMARY',
          payload: {
            winner: data.winner,
            winnerUsername: data.winner_username,
            heroOutcomes: data.hero_outcomes || null,
            finalTurn: data.final_turn,
            bossKilled: data.boss_killed || false,
            isDungeon: data.is_dungeon || false,
            battleScoreboard: data.battle_scoreboard || null,
            teamTotals: data.team_totals || null,
          },
        });
        setScreen('postmatch');
        break;
      case 'action_queued':
        dispatch({
          type: 'QUEUE_UPDATED',
          payload: {
            queue: data.queue || [{
              action_type: data.action_type,
              target_x: data.target_x,
              target_y: data.target_y,
            }],
            unit_id: data.unit_id || null,
            party: data.party || null,
          },
        });
        break;
      case 'queue_updated':
        dispatch({
          type: 'QUEUE_UPDATED',
          payload: { queue: data.queue || [], unit_id: data.unit_id || null, party: data.party || null },
        });
        break;
      case 'queue_cleared':
        dispatch({ type: 'QUEUE_CLEARED', payload: { unit_id: data.unit_id || null } });
        break;
      // Party control messages
      case 'party_member_selected':
        dispatch({ type: 'PARTY_MEMBER_SELECTED', payload: data });
        break;
      case 'party_member_released':
        dispatch({ type: 'PARTY_MEMBER_RELEASED', payload: data });
        break;
      case 'player_disconnected':
        dispatch({ type: 'PLAYER_DISCONNECTED', payload: data });
        break;
      case 'team_changed':
        dispatch({ type: 'TEAM_CHANGED', payload: data });
        break;
      case 'chat_message':
        dispatch({ type: 'CHAT_MESSAGE', payload: data });
        break;
      case 'config_changed':
        dispatch({ type: 'CONFIG_CHANGED', payload: data });
        break;
      case 'class_changed':
        dispatch({ type: 'CLASS_CHANGED', payload: data });
        break;
      // Phase 4E: Hero selection in lobby
      case 'hero_selected':
        dispatch({ type: 'HERO_SELECTED', payload: data });
        break;
      // Phase 4D: Inventory & Equipment WS messages
      case 'item_equipped':
        dispatch({ type: 'ITEM_EQUIPPED', payload: data });
        break;
      case 'item_unequipped':
        dispatch({ type: 'ITEM_UNEQUIPPED', payload: data });
        break;
      case 'item_transferred':
        dispatch({ type: 'ITEM_TRANSFERRED', payload: data });
        break;
      case 'party_inventory':
        dispatch({ type: 'PARTY_INVENTORY', payload: data });
        break;
      case 'player_stats_updated':
        dispatch({ type: 'PLAYER_STATS_UPDATED', payload: data });
        break;
      // Phase 7B-3: Group batch actions response — update queues for all units in the batch
      case 'group_batch_queued':
        dispatch({ type: 'GROUP_BATCH_QUEUED', payload: data });
        break;
      // Phase 7C-2: Stance WS responses
      case 'stance_updated':
        dispatch({ type: 'STANCE_UPDATED', payload: data });
        break;
      case 'all_stances_updated':
        dispatch({ type: 'ALL_STANCES_UPDATED', payload: data });
        break;
      // Phase 10C / 10G: Auto-target WS messages
      case 'auto_target_set':
        dispatch({ type: 'AUTO_TARGET_SET', payload: data });
        // Phase 10G: Differentiate combat log for skill vs melee auto-target
        if (data.skill_id) {
          dispatch({
            type: 'ADD_COMBAT_LOG',
            payload: { type: 'system', message: `✨ Auto-casting ${data.skill_name || data.skill_id} on: ${data.target_username || 'Unknown'}` },
          });
        } else {
          dispatch({
            type: 'ADD_COMBAT_LOG',
            payload: { type: 'system', message: `⚔ Auto-targeting: ${data.target_username || 'Unknown'}` },
          });
        }
        break;
      case 'auto_target_cleared':
        dispatch({ type: 'AUTO_TARGET_CLEARED', payload: data });
        // Phase 10E-3: Combat log message for auto-target cleared
        if (data.reason === 'target_died') {
          dispatch({
            type: 'ADD_COMBAT_LOG',
            payload: { type: 'system', message: '⚔ Target eliminated' },
          });
        } else if (data.reason === 'unreachable') {
          dispatch({
            type: 'ADD_COMBAT_LOG',
            payload: { type: 'system', message: '⚔ Target lost — unreachable' },
          });
        } else if (data.reason === 'cancelled') {
          dispatch({
            type: 'ADD_COMBAT_LOG',
            payload: { type: 'system', message: '⚔ Pursuit cancelled' },
          });
        }
        break;
      // Wave spawner messages
      case 'wave_started':
        dispatch({ type: 'WAVE_STARTED', payload: data });
        // Phase 15D: Wave clear — previous wave was beaten, new one spawning
        if (audioManager.current) audioManager.current.processEvent('wave_clear');
        break;
      // Phase 12-5: Floor transition
      case 'floor_advance':
        dispatch({ type: 'FLOOR_ADVANCE', payload: data });
        // Phase 15D: Floor descend audio
        if (audioManager.current) audioManager.current.processEvent('floor_descend');
        break;
      case 'error':
        console.error('[WS] Server error:', data.message);
        dispatch({ type: 'SET_LOBBY_ERROR', payload: data.message });
        break;
      default:
        console.log('[WS] Unhandled message:', data);
    }
  }, [dispatch]);

  // Single WebSocket connection — opens when matchId+playerId exist, stays open
  // until LEAVE_MATCH clears them (which sets matchId/playerId to null)
  const { sendAction, wsReady } = useWebSocket(
    gameState.matchId,
    gameState.playerId,
    handleMessage,
  );

  const handleLeaveMatch = () => {
    dispatch({ type: 'LEAVE_MATCH' });
    // If we have a username, go to town instead of lobby
    if (gameState.username) {
      setScreen('town');
    } else {
      setScreen('lobby');
    }
  };

  const handleBackToTown = () => {
    dispatch({ type: 'LEAVE_MATCH' });
    dispatch({ type: 'CLEAR_POST_MATCH' });
    setScreen('town');
  };

  const handleEnterArena = async () => {
    // Create a PvP arena match directly from Town Hub (no need to return to lobby)
    try {
      const body = {
        request: { username: gameState.username },
        config: {
          map_id: 'arena_classic',
          match_type: 'pvp',
          ai_opponents: 0,
          ai_allies: 0,
        },
      };
      const res = await apiFetch('/api/lobby/create', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      });
      if (!res.ok) throw new Error('Failed to create match');
      const data = await res.json();

      dispatch({
        type: 'JOIN_MATCH',
        payload: {
          matchId: data.match_id,
          playerId: data.player_id,
          players: data.players || {},
          config: data.config || null,
          chat: [],
        },
      });
      setScreen('waiting');
    } catch (err) {
      console.error('[App] Failed to create arena match:', err);
    }
  };

  const handleEnterDungeon = async (heroIds) => {
    // Create a dungeon match with the selected heroes (up to 4)
    // Default to procedural WFC map — host can change map in the WaitingRoom dropdown
    try {
      const mapId = 'procedural';
      const body = {
        request: { username: gameState.username },
        config: {
          map_id: mapId,
          match_type: 'dungeon',
          ai_opponents: 0,
          ai_allies: 0,
        },
      };
      const res = await apiFetch('/api/lobby/create', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      });
      if (!res.ok) throw new Error('Failed to create dungeon match');
      const data = await res.json();

      dispatch({
        type: 'JOIN_MATCH',
        payload: {
          matchId: data.match_id,
          playerId: data.player_id,
          players: data.players || {},
          config: data.config || null,
          chat: [],
        },
      });
      // selectedHeroIds is already set from HeroRoster toggles — no need to re-dispatch
      setScreen('waiting');
    } catch (err) {
      console.error('[App] Failed to create dungeon match:', err);
    }
  };

  const handleJoinMatch = async (matchId) => {
    // Join an existing match from TownHub browse panel
    try {
      const res = await apiFetch(`/api/lobby/join/${matchId}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username: gameState.username }),
      });
      if (!res.ok) {
        const errData = await res.json().catch(() => ({}));
        throw new Error(errData.detail || 'Failed to join match');
      }
      const data = await res.json();

      dispatch({
        type: 'JOIN_MATCH',
        payload: {
          matchId: data.match_id,
          playerId: data.player_id,
          players: data.players || {},
          config: data.config || null,
          chat: data.chat || [],
        },
      });
      setScreen('waiting');
    } catch (err) {
      console.error('[App] Failed to join match:', err);
    }
  };

  return (
    <AudioProvider audioManager={audioManager} playUI={playUI} volumeControls={volumeControls}>
    <div className={`app${screen === 'arena' ? ' app--fullscreen' : ''}`} onClick={resumeAudio}>
      <VolumeSettings />

      <main>
        {screen === 'lobby' && (
          <div key={`lobby-${screenKeyRef.current}`} className="screen-enter">
            <Lobby
              onEnterWaiting={() => setScreen('waiting')}
              onEnterTown={() => setScreen('town')}
            />
          </div>
        )}
        {screen === 'town' && (
          <div key={`town-${screenKeyRef.current}`} className="screen-enter">
            <TownHub
              onEnterArena={handleEnterArena}
              onEnterDungeon={handleEnterDungeon}
              onJoinMatch={handleJoinMatch}
            />
          </div>
        )}
        {screen === 'waiting' && (
          <div key={`waiting-${screenKeyRef.current}`} className="screen-enter">
            <WaitingRoom
              sendAction={sendAction}
              onLeave={handleLeaveMatch}
              wsReady={wsReady}
            />
          </div>
        )}
        {screen === 'arena' && (
          <Arena
            sendAction={sendAction}
            onMatchEnd={handleLeaveMatch}
            audioManager={audioManager}
          />
        )}
        {screen === 'postmatch' && (
          <div key={`postmatch-${screenKeyRef.current}`} className="screen-enter">
            <PostMatchScreen
              onBackToTown={handleBackToTown}
              onLeave={handleLeaveMatch}
            />
          </div>
        )}
      </main>
    </div>
    </AudioProvider>
  );
}

/**
 * Main application — wraps AppInner in GameStateProvider.
 */
export default function App() {
  return (
    <GameStateProvider>
      <AppInner />
    </GameStateProvider>
  );
}
