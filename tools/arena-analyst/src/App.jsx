import React, { useState, useEffect } from 'react';
import MatchList from './components/MatchList.jsx';
import MatchDetail from './components/MatchDetail.jsx';
import ClassBalance from './components/ClassBalance.jsx';
import CompAnalysis from './components/CompAnalysis.jsx';
import Timeline from './components/Timeline.jsx';
import TrendCharts from './components/TrendCharts.jsx';
import './styles/main.css';

const TABS = [
  { id: 'history',     label: 'Match History' },
  { id: 'detail',      label: 'Match Detail' },
  { id: 'class',       label: 'Class Balance' },
  { id: 'composition', label: 'Compositions' },
  { id: 'timeline',    label: 'Timeline' },
  { id: 'trends',      label: 'Trends' },
];

export default function App() {
  const [activeTab, setActiveTab] = useState('history');
  const [matches, setMatches] = useState([]);
  const [selectedMatch, setSelectedMatch] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  // Fetch match list on mount
  useEffect(() => {
    fetchMatches();
  }, []);

  async function fetchMatches() {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch('/api/matches');
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      setMatches(data);
    } catch (err) {
      setError(err.message);
      setMatches([]);
    } finally {
      setLoading(false);
    }
  }

  async function fetchMatchDetail(matchId) {
    try {
      const res = await fetch(`/api/matches/${matchId}`);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      setSelectedMatch(data);
      setActiveTab('detail');
    } catch (err) {
      setError(err.message);
    }
  }

  function renderTabContent() {
    switch (activeTab) {
      case 'history':
        return (
          <MatchList
            matches={matches}
            loading={loading}
            error={error}
            onRefresh={fetchMatches}
            onSelectMatch={fetchMatchDetail}
          />
        );
      case 'detail':
        return (
          <MatchDetail
            match={selectedMatch}
            onBack={() => setActiveTab('history')}
          />
        );
      case 'class':
        return <ClassBalance />;
      case 'composition':
        return <CompAnalysis />;
      case 'timeline':
        return <Timeline matches={matches} />;
      case 'trends':
        return <TrendCharts />;
      default:
        return null;
    }
  }

  return (
    <div className="app">
      <header className="app-header">
        <h1 className="app-title">Arena Analyst</h1>
        <span className="app-subtitle">Match Tracker & Balance Tool</span>
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
        {renderTabContent()}
      </main>
    </div>
  );
}
