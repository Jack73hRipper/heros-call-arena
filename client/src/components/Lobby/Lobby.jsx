import React, { useState, useEffect, useCallback } from 'react';
import { useGameState, useGameDispatch } from '../../context/GameStateContext';
import { fetchWithRetry } from '../../utils/fetchWithRetry';

// Fallback if server unreachable
const FALLBACK_MAPS = [
  { id: 'arena_classic', label: 'Arena Classic 15×15' },
];

/**
 * Lobby screen — create or join a match.
 * Phase 2: Map selection, match type, AI configuration.
 */
export default function Lobby({ onEnterWaiting, onEnterTown }) {
  const gameState = useGameState();
  const dispatch = useGameDispatch();
  const [username, setUsername] = useState(gameState.username || '');
  const [hasEnteredName, setHasEnteredName] = useState(!!gameState.username);
  const [matches, setMatches] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [maps, setMaps] = useState(FALLBACK_MAPS);

  // Fetch available maps from server on mount (retries if backend is still starting)
  useEffect(() => {
    fetchWithRetry('/api/maps/')
      .then(res => res.ok ? res.json() : Promise.reject('Failed'))
      .then(data => { if (data.length > 0) setMaps(data); })
      .catch(() => console.warn('[Lobby] Could not fetch maps, using fallback'));
  }, []);

  // Match creation config (defaults — host configures in WaitingRoom after creation)
  const [selectedMap] = useState('arena_classic');
  const [matchType] = useState('pvp');
  const [aiOpponents] = useState(0);
  const [aiAllies] = useState(0);

  // Fetch match list from server
  const fetchMatches = useCallback(async () => {
    try {
      const res = await fetch('/api/lobby/matches');
      if (res.ok) {
        const data = await res.json();
        setMatches(data);
      }
    } catch (err) {
      console.error('[Lobby] Failed to fetch matches:', err);
    }
  }, []);

  // Poll for matches every 3 seconds while on lobby screen
  useEffect(() => {
    if (!hasEnteredName) return;
    fetchMatches();
    const interval = setInterval(fetchMatches, 3000);
    return () => clearInterval(interval);
  }, [hasEnteredName, fetchMatches]);

  const handleEnterArena = (e) => {
    e.preventDefault();
    const trimmed = username.trim();
    if (!trimmed) return;
    dispatch({ type: 'SET_USERNAME', payload: trimmed });
    // Skip the lobby screen — go straight to Town Hub
    if (onEnterTown) {
      onEnterTown();
    } else {
      setHasEnteredName(true);
    }
  };

  const handleCreateMatch = async () => {
    setLoading(true);
    setError(null);
    try {
      const body = {
        request: { username: gameState.username },
        config: {
          map_id: selectedMap,
          match_type: matchType,
          ai_opponents: matchType === 'pvp' ? 0 : aiOpponents,
          ai_allies: matchType === 'pvp' ? 0 : aiAllies,
        },
      };
      const res = await fetch('/api/lobby/create', {
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
          players: data.players || {
            [data.player_id]: {
              username: data.username,
              position: data.position,
              hp: 100,
              max_hp: 100,
              is_alive: true,
              is_ready: false,
            },
          },
          config: data.config || null,
          chat: [],
        },
      });
      onEnterWaiting();
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleJoinMatch = async (matchId) => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(`/api/lobby/join/${matchId}`, {
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
      onEnterWaiting();
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  // Username entry screen — Phase 15 Chunk 2: Immersive Title Screen
  if (!hasEnteredName) {
    return (
      <div className="lobby lobby-landing">
        <div className="lobby-landing-inner">
          {/* Login Card — uses grim-frame system */}
          <div className="lobby-landing-card grim-frame grim-frame--ember">
            <h2 className="grim-header">Enter the Arena</h2>

            <p className="lobby-landing-flavor">
              Steel yourself, warrior. Glory awaits those bold enough to answer the call.
            </p>

            <div className="grim-separator grim-separator--subtle">⬥</div>

            <form className="username-form" onSubmit={handleEnterArena}>
              <input
                type="text"
                placeholder="Speak thy name..."
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                maxLength={20}
                autoFocus
              />
              <button
                type="submit"
                className="grim-btn grim-btn--lg grim-btn--ember grim-btn--full"
                disabled={!username.trim()}
              >
                Enter Arena
              </button>
            </form>

            <div className="grim-separator grim-separator--subtle">⬥</div>
          </div>

          {/* Version / credits line */}
          <p className="lobby-version">Phase 15 · Arena Prototype</p>
        </div>
      </div>
    );
  }

  // Filter to joinable matches (waiting status, not full, non-dungeon/pvpve)
  // Dungeon and PVPVE matches should be joined from TownHub where heroes can be selected
  const joinableMatches = matches.filter(
    (m) => m.status === 'waiting' && m.player_count < m.max_players && m.match_type !== 'dungeon' && m.match_type !== 'pvpve'
  );

  return (
    <div className="lobby">
      <div className="lobby-header">
        <h2>Lobby</h2>
        <p className="welcome-msg">Welcome, <strong>{gameState.username}</strong></p>
      </div>

      {error && <p className="error-msg">{error}</p>}

      <div className="lobby-actions">
        <button className="btn-create" onClick={handleCreateMatch} disabled={loading}>
          {loading ? 'Creating...' : 'Create Match'}
        </button>
        {onEnterTown && (
          <button className="btn-town" onClick={onEnterTown}>
            Town Hub
          </button>
        )}
      </div>

      <div className="match-list">
        <h3>Available Matches ({joinableMatches.length})</h3>
        {joinableMatches.length === 0 ? (
          <p className="placeholder">No matches available — create one!</p>
        ) : (
          <ul className="match-list-items">
            {joinableMatches.map((match) => (
              <li key={match.match_id} className="match-list-item">
                <div className="match-info">
                  <span className="match-id">#{match.match_id}</span>
                  <span className="match-players">
                    {match.player_count}/{match.max_players} players
                  </span>
                  <span className="match-map">
                    {maps.find((m) => m.id === match.map_id)?.label || match.map_id}
                  </span>
                  <span className={`match-type-tag tag-${match.match_type || 'pvp'}`}>
                    {(match.match_type || 'pvp').toUpperCase().replace('_', ' ')}
                  </span>
                  {match.ai_opponents > 0 && (
                    <span className="match-ai">{match.ai_opponents} AI</span>
                  )}
                </div>
                <button
                  className="btn-join"
                  onClick={() => handleJoinMatch(match.match_id)}
                  disabled={loading}
                >
                  Join
                </button>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}
