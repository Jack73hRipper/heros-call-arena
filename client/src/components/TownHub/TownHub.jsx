import React, { useState, useEffect, useCallback, useRef } from 'react';
import { useGameState, useGameDispatch } from '../../context/GameStateContext';
import { fetchWithRetry } from '../../utils/fetchWithRetry';
import HiringHall from './HiringHall';
import HeroRoster from './HeroRoster';
import Merchant from './Merchant';
import Bank from './Bank';
import EscapeMenu from '../EscapeMenu/EscapeMenu';

/**
 * TownHub — main town screen with sidebar navigation.
 *
 * Phase 15 Chunk 3: Replaced horizontal tab bar with sidebar navigation panel.
 * Layout: sidebar (locations) + content area (framed panel), responsive collapse at 900px.
 *
 * Tabs: Hero Roster, Hiring Hall, Merchant, Bank, Browse Matches
 * Features: Gold display, Enter Arena bypass, Enter Dungeon with hero selection,
 *           Browse and join existing matches (PvP and dungeon).
 */

const NAV_ITEMS = [
  { id: 'roster', label: 'Roster', icon: '⚔' },
  { id: 'hiring', label: 'Hiring Hall', icon: '🏛' },
  { id: 'merchant', label: 'Merchant', icon: '🪙' },
  { id: 'bank', label: 'Bank', icon: '🏦' },
  { id: 'browse', label: 'Notice Board', icon: '📜' },
];

const CONTENT_TITLES = {
  roster: 'Hero Roster',
  hiring: 'Hiring Hall',
  merchant: 'Merchant',
  bank: 'Bank Vault',
  browse: 'The Notice Board',
};

export default function TownHub({ onEnterArena, onEnterDungeon, onJoinMatch }) {
  const gameState = useGameState();
  const dispatch = useGameDispatch();
  const [activeTab, setActiveTab] = useState('roster');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [matches, setMatches] = useState([]);
  const [joiningMatchId, setJoiningMatchId] = useState(null);
  const [showEscMenu, setShowEscMenu] = useState(false);

  const availableClasses = gameState.availableClasses || {};
  const gold = gameState.gold;
  const selectedHeroIds = gameState.selectedHeroIds || [];

  // Escape key — toggle town ESC menu
  useEffect(() => {
    const handleEscapeKey = (e) => {
      if (e.key !== 'Escape') return;
      if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') return;
      e.preventDefault();
      setShowEscMenu(prev => !prev);
    };
    window.addEventListener('keydown', handleEscapeKey);
    return () => window.removeEventListener('keydown', handleEscapeKey);
  }, []);

  // Gold flash animation — detect gold changes and briefly pulse
  const prevGoldRef = useRef(gold);
  const [goldFlash, setGoldFlash] = useState(false);
  useEffect(() => {
    if (prevGoldRef.current !== gold && prevGoldRef.current != null) {
      setGoldFlash(true);
      const timer = setTimeout(() => setGoldFlash(false), 650);
      prevGoldRef.current = gold;
      return () => clearTimeout(timer);
    }
    prevGoldRef.current = gold;
  }, [gold]);

  // Fetch profile + tavern data on mount
  const fetchProfile = useCallback(async () => {
    if (!gameState.username) return;
    setLoading(true);
    try {
      const [profileRes, tavernRes] = await Promise.all([
        fetchWithRetry(`/api/town/profile?username=${encodeURIComponent(gameState.username)}`),
        fetchWithRetry(`/api/town/tavern?username=${encodeURIComponent(gameState.username)}`),
      ]);

      if (profileRes.ok) {
        const profileData = await profileRes.json();
        dispatch({
          type: 'SET_PROFILE',
          payload: {
            gold: profileData.profile.gold,
            heroes: profileData.heroes,
            bank: profileData.bank || [],
          },
        });
      }

      if (tavernRes.ok) {
        const tavernData = await tavernRes.json();
        dispatch({
          type: 'SET_TAVERN',
          payload: {
            heroes: tavernData.heroes,
            gold: tavernData.gold,
          },
        });
      }
    } catch (err) {
      setError('Failed to load town data');
      console.error('[TownHub] Fetch error:', err);
    } finally {
      setLoading(false);
    }
  }, [gameState.username, dispatch]);

  useEffect(() => {
    fetchProfile();
  }, [fetchProfile]);

  // Poll for joinable matches every 3 seconds
  const fetchMatches = useCallback(async () => {
    try {
      const res = await fetch('/api/lobby/matches');
      if (res.ok) {
        const data = await res.json();
        setMatches(data);
      }
    } catch (err) {
      console.error('[TownHub] Failed to fetch matches:', err);
    }
  }, []);

  useEffect(() => {
    fetchMatches();
    const interval = setInterval(fetchMatches, 3000);
    return () => clearInterval(interval);
  }, [fetchMatches]);

  // Filter to joinable matches (waiting, not full)
  const joinableMatches = matches.filter(
    (m) => m.status === 'waiting' && m.player_count < m.max_players
  );

  // Build count map for nav badges
  const navCounts = {
    roster: (gameState.heroes || []).filter(h => h.is_alive).length,
    bank: (gameState.bank || []).length,
    browse: joinableMatches.length,
  };

  const handleJoinMatch = async (matchId, matchType) => {
    if (matchType === 'dungeon' && (!selectedHeroIds || selectedHeroIds.length === 0)) {
      setError('Select at least one hero from your roster before joining a dungeon!');
      setActiveTab('roster');
      return;
    }
    setJoiningMatchId(matchId);
    try {
      await onJoinMatch(matchId);
    } catch (err) {
      setError(err.message || 'Failed to join match');
    } finally {
      setJoiningMatchId(null);
    }
  };

  const handleEnterDungeon = () => {
    if (!selectedHeroIds || selectedHeroIds.length === 0) {
      setError('Select at least one hero from your roster first!');
      setActiveTab('roster');
      return;
    }
    onEnterDungeon(selectedHeroIds);
  };

  const handleHeroSelected = (heroId) => {
    setError(null);
  };

  if (loading) {
    return (
      <div className="town-hub">
        <div className="town-hub-sidebar grim-frame">
          <div className="town-sidebar-title">
            <h2 className="grim-header grim-header--left">Town Hub</h2>
          </div>
        </div>
        <div className="town-hub-content grim-frame">
          <p className="town-loading">Loading town data...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="town-hub">
      {/* ===== Sidebar Navigation ===== */}
      <aside className="town-hub-sidebar grim-frame">
        {/* Sidebar header */}
        <div className="town-sidebar-header">
          <h2 className="town-sidebar-title">Town Hub</h2>
          <span className="town-welcome">Welcome, <strong>{gameState.username}</strong></span>
        </div>

        <div className="grim-separator grim-separator--ember">◆</div>

        {/* Navigation items */}
        <nav className="town-sidebar-nav">
          {NAV_ITEMS.map((item) => (
            <button
              key={item.id}
              className={`town-nav-item ${activeTab === item.id ? 'town-nav-item--active' : ''}`}
              onClick={() => setActiveTab(item.id)}
            >
              <span className="town-nav-icon">{item.icon}</span>
              <span className="town-nav-label">{item.label}</span>
              {navCounts[item.id] != null && (
                <span className="town-nav-count">{navCounts[item.id]}</span>
              )}
            </button>
          ))}
        </nav>

        <div className="grim-separator grim-separator--subtle">⬥</div>

        {/* Gold display */}
        <div className="town-sidebar-gold">
          <span className="town-gold-label">Gold</span>
          <span className={`gold-display${goldFlash ? ' gold-flash' : ''}`}>{gold}g</span>
        </div>

        <div className="grim-separator grim-separator--subtle">⬥</div>

        {/* Action buttons in sidebar */}
        <div className="town-sidebar-actions">
          <button className="grim-btn grim-btn--verdant grim-btn--full grim-btn-pulse--verdant" onClick={handleEnterDungeon}>
            Enter Dungeon
            {selectedHeroIds.length > 0 && (
              <span className="selected-hero-name">
                {' '}({selectedHeroIds.length})
              </span>
            )}
          </button>
          <button className="grim-btn grim-btn--crimson grim-btn--full grim-btn-pulse--crimson" onClick={onEnterArena}>
            Enter Arena
          </button>
        </div>
      </aside>

      {/* ===== Content Area ===== */}
      <main className="town-hub-content grim-frame">
        {/* Content header */}
        <div className="town-content-header">
          <h3 className="grim-header grim-header--left">{CONTENT_TITLES[activeTab]}</h3>
        </div>

        {error && <p className="town-error">{error}</p>}

        {/* Tab content body */}
        <div className="town-content-body">
          {activeTab === 'roster' && (
            <HeroRoster
              availableClasses={availableClasses}
              onSelectHero={handleHeroSelected}
            />
          )}
          {activeTab === 'hiring' && (
            <HiringHall availableClasses={availableClasses} />
          )}
          {activeTab === 'merchant' && (
            <Merchant availableClasses={availableClasses} />
          )}
          {activeTab === 'bank' && (
            <Bank availableClasses={availableClasses} />
          )}
          {activeTab === 'browse' && (
            <div className="town-browse-matches">
              <h3>Available Matches ({joinableMatches.length})</h3>
              {joinableMatches.length === 0 ? (
                <p className="town-placeholder">No adventurers seeking companions — post your own quest!</p>
              ) : (
                <ul className="town-match-list">
                  {joinableMatches.map((match) => {
                    const isDungeon = match.match_type === 'dungeon';
                    const typeLabel = (match.match_type || 'pvp').toUpperCase().replace('_', ' ');
                    return (
                      <li key={match.match_id} className="town-match-item">
                        <div className="town-match-info">
                          <span className="town-match-id">#{match.match_id}</span>
                          <span className="town-match-players">
                            {match.player_count}/{match.max_players} players
                          </span>
                          <span className="town-match-map">{match.map_id}</span>
                          <span className={`match-type-tag tag-${match.match_type || 'pvp'}`}>
                            {typeLabel}
                          </span>
                          {isDungeon && selectedHeroIds.length === 0 && (
                            <span className="town-match-warning">Select heroes first</span>
                          )}
                        </div>
                        <button
                          className={`btn-join-town ${isDungeon ? 'btn-join-dungeon' : ''}`}
                          onClick={() => handleJoinMatch(match.match_id, match.match_type)}
                          disabled={joiningMatchId === match.match_id}
                        >
                          {joiningMatchId === match.match_id ? 'Joining...' : 'Join'}
                        </button>
                      </li>
                    );
                  })}
                </ul>
              )}
              {selectedHeroIds.length > 0 && (
                <p className="town-browse-hint">
                  {selectedHeroIds.length} hero{selectedHeroIds.length > 1 ? 'es' : ''} selected for dungeon
                </p>
              )}
            </div>
          )}
        </div>
      </main>

      {/* Phase 15: ESC Menu Overlay (town context — Quit Game instead of Surrender) */}
      {showEscMenu && (
        <EscapeMenu
          onResume={() => setShowEscMenu(false)}
          context="town"
        />
      )}
    </div>
  );
}
