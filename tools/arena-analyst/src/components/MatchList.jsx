import React, { useState, useMemo } from 'react';

// ── Class color map ────────────────────────────────────
const CLASS_COLORS = {
  crusader:      '#4a8fd0',
  confessor:     '#f0c040',
  inquisitor:    '#a0a0a0',
  ranger:        '#44aa44',
  hexblade:      '#cc44cc',
  mage:          '#5588cc',
  bard:          '#e08040',
  blood_knight:  '#cc3333',
  plague_doctor: '#66cc66',
  revenant:      '#8888cc',
  shaman:        '#44cccc',
};

function classColor(classId) {
  return CLASS_COLORS[classId] || '#888';
}

function formatClassName(classId) {
  if (!classId) return '—';
  return classId.split('_').map(w => w[0].toUpperCase() + w.slice(1)).join(' ');
}

function formatDate(ts) {
  if (!ts) return '—';
  const d = new Date(ts);
  return d.toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' })
    + ' ' + d.toLocaleTimeString(undefined, { hour: '2-digit', minute: '2-digit' });
}

function formatWinner(w) {
  if (!w) return '—';
  if (w === 'team_a') return 'Team A';
  if (w === 'team_b') return 'Team B';
  if (w === 'draw') return 'Draw';
  if (w === 'party_wipe') return 'Party Wipe';
  return w;
}

export default function MatchList({ matches, loading, error, onRefresh, onSelectMatch }) {
  const [filterType, setFilterType] = useState('');
  const [filterMap, setFilterMap] = useState('');
  const [filterFrom, setFilterFrom] = useState('');
  const [filterTo, setFilterTo] = useState('');
  const [searchTerm, setSearchTerm] = useState('');

  // Derive unique types and maps for dropdowns
  const { types, maps } = useMemo(() => {
    const ts = new Set();
    const ms = new Set();
    for (const m of matches) {
      if (m.match_type) ts.add(m.match_type);
      if (m.map_id) ms.add(m.map_id);
    }
    return {
      types: [...ts].sort(),
      maps: [...ms].sort(),
    };
  }, [matches]);

  // Client-side filtering (server also supports it, but local is snappier)
  const filtered = useMemo(() => {
    let result = matches;
    if (filterType) {
      result = result.filter(m => m.match_type === filterType);
    }
    if (filterMap) {
      result = result.filter(m => m.map_id === filterMap);
    }
    if (filterFrom) {
      const fromDate = new Date(filterFrom);
      result = result.filter(m => m.timestamp && new Date(m.timestamp) >= fromDate);
    }
    if (filterTo) {
      const toDate = new Date(filterTo);
      toDate.setDate(toDate.getDate() + 1);
      result = result.filter(m => m.timestamp && new Date(m.timestamp) < toDate);
    }
    if (searchTerm) {
      const term = searchTerm.toLowerCase();
      result = result.filter(m =>
        (m.match_id && m.match_id.toLowerCase().includes(term)) ||
        (m.mvp && m.mvp.toLowerCase().includes(term)) ||
        (m.map_id && m.map_id.toLowerCase().includes(term))
      );
    }
    return result;
  }, [matches, filterType, filterMap, filterFrom, filterTo, searchTerm]);

  const hasFilters = filterType || filterMap || filterFrom || filterTo || searchTerm;

  function clearFilters() {
    setFilterType('');
    setFilterMap('');
    setFilterFrom('');
    setFilterTo('');
    setSearchTerm('');
  }

  return (
    <div className="tab-content">
      <div className="tab-header">
        <h2>Match History</h2>
        <div className="header-actions">
          <span className="match-count">
            {filtered.length}{hasFilters ? ` / ${matches.length}` : ''} match{filtered.length !== 1 ? 'es' : ''}
          </span>
          <button className="btn btn-secondary" onClick={onRefresh}>Refresh</button>
        </div>
      </div>

      {/* ── Filter bar ── */}
      <div className="filter-bar">
        <div className="filter-group">
          <label className="filter-label">Type</label>
          <select className="filter-select" value={filterType} onChange={e => setFilterType(e.target.value)}>
            <option value="">All</option>
            {types.map(t => <option key={t} value={t}>{t}</option>)}
          </select>
        </div>

        <div className="filter-group">
          <label className="filter-label">Map</label>
          <select className="filter-select" value={filterMap} onChange={e => setFilterMap(e.target.value)}>
            <option value="">All</option>
            {maps.map(m => <option key={m} value={m}>{m}</option>)}
          </select>
        </div>

        <div className="filter-group">
          <label className="filter-label">From</label>
          <input type="date" className="filter-input" value={filterFrom} onChange={e => setFilterFrom(e.target.value)} />
        </div>

        <div className="filter-group">
          <label className="filter-label">To</label>
          <input type="date" className="filter-input" value={filterTo} onChange={e => setFilterTo(e.target.value)} />
        </div>

        <div className="filter-group filter-search">
          <label className="filter-label">Search</label>
          <input
            type="text"
            className="filter-input"
            placeholder="ID, MVP, map..."
            value={searchTerm}
            onChange={e => setSearchTerm(e.target.value)}
          />
        </div>

        {hasFilters && (
          <button className="btn btn-small filter-clear-btn" onClick={clearFilters}>Clear</button>
        )}
      </div>

      {/* ── States ── */}
      {loading && <div className="loading">Loading matches...</div>}
      {error && <div className="error-msg">Error: {error}</div>}
      {!loading && !error && matches.length === 0 && (
        <div className="empty-state">
          <div className="empty-icon">📊</div>
          <p>No match reports found.</p>
          <p className="hint">Play some matches to generate data in <code>server/data/match_history/</code></p>
        </div>
      )}
      {!loading && !error && matches.length > 0 && filtered.length === 0 && (
        <div className="empty-state">
          <p>No matches match your filters.</p>
          <button className="btn btn-secondary" onClick={clearFilters}>Clear Filters</button>
        </div>
      )}

      {/* ── Match table ── */}
      {!loading && filtered.length > 0 && (
        <table className="match-table">
          <thead>
            <tr>
              <th>Date</th>
              <th>Map</th>
              <th>Type</th>
              <th>Winner</th>
              <th>Turns</th>
              <th>Score</th>
              <th>MVP</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {filtered.map(m => (
              <tr key={m.match_id || m.filename} onClick={() => onSelectMatch(m.match_id)}>
                <td className="td-date">{formatDate(m.timestamp)}</td>
                <td>{m.map_id ? m.map_id.replace(/_/g, ' ') : '—'}</td>
                <td><span className={`type-badge type-${m.match_type}`}>{m.match_type || '—'}</span></td>
                <td className={`winner-${m.winner}`}>{formatWinner(m.winner)}</td>
                <td className="td-num">{m.duration_turns ?? '—'}</td>
                <td className="td-score">
                  <span className="score-a">{m.team_a_kills ?? 0}</span>
                  <span className="score-dash">–</span>
                  <span className="score-b">{m.team_b_kills ?? 0}</span>
                </td>
                <td className="td-mvp">{m.mvp || '—'}</td>
                <td><button className="btn btn-small btn-view">View</button></td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
