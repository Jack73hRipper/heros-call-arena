import React, { useState, useEffect } from 'react';
import MatchBrowser from './components/MatchBrowser.jsx';
import TeamScoreboard from './components/TeamScoreboard.jsx';
import CombatTimeline from './components/CombatTimeline.jsx';
import ExplorationInspector from './components/ExplorationInspector.jsx';
import EquipmentReport from './components/EquipmentReport.jsx';
import BatchOverview from './components/BatchOverview.jsx';
import './styles/main.css';

const TABS = [
  { id: 'browser',     label: 'Match Browser' },
  { id: 'scoreboard',  label: '4-Team Scoreboard' },
  { id: 'timeline',    label: 'Combat Timeline' },
  { id: 'exploration', label: 'Exploration' },
  { id: 'equipment',   label: 'Equipment' },
  { id: 'batch',       label: 'Batch Overview' },
];

export default function App() {
  const [activeTab, setActiveTab] = useState('browser');
  const [matches, setMatches] = useState([]);
  const [selectedMatch, setSelectedMatch] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => { fetchMatches(); }, []);

  async function fetchMatches() {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch('/api/matches');
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      setMatches(await res.json());
    } catch (err) {
      setError(err.message);
      setMatches([]);
    } finally {
      setLoading(false);
    }
  }

  async function selectMatch(matchId) {
    try {
      const res = await fetch(`/api/matches/${matchId}`);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      setSelectedMatch(data);
      setActiveTab('scoreboard');
    } catch (err) {
      setError(err.message);
    }
  }

  function renderTab() {
    switch (activeTab) {
      case 'browser':
        return <MatchBrowser matches={matches} loading={loading} error={error}
                             onRefresh={fetchMatches} onSelect={selectMatch} />;
      case 'scoreboard':
        return <TeamScoreboard match={selectedMatch} onBack={() => setActiveTab('browser')} />;
      case 'timeline':
        return <CombatTimeline match={selectedMatch} onBack={() => setActiveTab('browser')} />;
      case 'exploration':
        return <ExplorationInspector match={selectedMatch} onBack={() => setActiveTab('browser')} />;
      case 'equipment':
        return <EquipmentReport match={selectedMatch} onBack={() => setActiveTab('browser')} />;
      case 'batch':
        return <BatchOverview />;
      default:
        return null;
    }
  }

  return (
    <div className="app">
      <header className="app-header">
        <h1 className="app-title">PVPVE Analyst</h1>
        <span className="app-subtitle">4-Team Dungeon Match Dashboard</span>
        {selectedMatch && (
          <span className="app-match-tag">
            Match: {selectedMatch.match_id?.substring(0, 8)}
          </span>
        )}
      </header>
      <nav className="tab-bar">
        {TABS.map(tab => (
          <button
            key={tab.id}
            className={`tab-btn ${activeTab === tab.id ? 'active' : ''}`}
            onClick={() => setActiveTab(tab.id)}
          >
            {tab.label}
          </button>
        ))}
      </nav>
      <main className="app-main">
        {renderTab()}
      </main>
    </div>
  );
}
