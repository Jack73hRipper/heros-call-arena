import React, { useState, useMemo } from 'react';

const TEAM_LABELS = { a: 'Team A', b: 'Team B', c: 'Team C', d: 'Team D', draw: 'Draw',
                      team_a: 'Team A', team_b: 'Team B', team_c: 'Team C', team_d: 'Team D' };

function winnerClass(w) {
  if (!w) return '';
  return `winner-${w.replace('team_', '')}`;
}

function winnerLabel(w) {
  return TEAM_LABELS[w] || w || '—';
}

function formatDate(ts) {
  if (!ts) return '—';
  const d = new Date(ts);
  return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' });
}

export default function MatchBrowser({ matches, loading, error, onRefresh, onSelect }) {
  const [winnerFilter, setWinnerFilter] = useState('');
  const [search, setSearch] = useState('');

  const filtered = useMemo(() => {
    let list = matches || [];
    if (winnerFilter) {
      list = list.filter(m => {
        const w = (m.winner || '').replace('team_', '');
        return w === winnerFilter;
      });
    }
    if (search) {
      const q = search.toLowerCase();
      list = list.filter(m =>
        (m.match_id || '').toLowerCase().includes(q) ||
        (m.mvp || '').toLowerCase().includes(q)
      );
    }
    return list;
  }, [matches, winnerFilter, search]);

  if (loading) return <div className="loading">Loading PVPVE matches...</div>;
  if (error) return <div className="error-msg">Error: {error}</div>;

  return (
    <div className="tab-content">
      <div className="tab-header">
        <h2>PVPVE Match Browser</h2>
        <div className="header-actions">
          <span style={{ fontSize: 12, color: 'var(--text-dim)' }}>{filtered.length} matches</span>
          <button className="btn btn-small" onClick={onRefresh}>Refresh</button>
        </div>
      </div>

      <div className="filter-bar">
        <div className="filter-group">
          <span className="filter-label">Winner</span>
          <select className="filter-select" value={winnerFilter}
                  onChange={e => setWinnerFilter(e.target.value)}>
            <option value="">All</option>
            <option value="a">Team A</option>
            <option value="b">Team B</option>
            <option value="c">Team C</option>
            <option value="d">Team D</option>
            <option value="draw">Draw</option>
          </select>
        </div>
        <div className="filter-group" style={{ flex: 1 }}>
          <span className="filter-label">Search</span>
          <input className="filter-input" placeholder="Match ID or MVP..."
                 value={search} onChange={e => setSearch(e.target.value)} />
        </div>
      </div>

      {filtered.length === 0 ? (
        <div className="empty-state">
          <div className="empty-icon">⚔</div>
          <p>No PVPVE matches found</p>
          <p className="hint">Run <code>start-batch-pvpve.bat</code> to generate match data</p>
        </div>
      ) : (
        <table className="match-table">
          <thead>
            <tr>
              <th>Date</th>
              <th>Match ID</th>
              <th>Winner</th>
              <th className="td-num">Turns</th>
              <th className="td-num">Heroes</th>
              <th className="td-num">PVE</th>
              <th>MVP</th>
              <th>Team Kills</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {filtered.map(m => {
              const ts = m.team_stats || {};
              return (
                <tr key={m.match_id} onClick={() => onSelect(m.match_id)}>
                  <td className="td-date">{formatDate(m.timestamp)}</td>
                  <td style={{ fontFamily: 'monospace', fontSize: 12 }}>{(m.match_id || '').substring(0, 8)}</td>
                  <td><span className={winnerClass(m.winner)}>{winnerLabel(m.winner)}</span></td>
                  <td className="td-num">{m.duration_turns || '—'}</td>
                  <td className="td-num">{m.hero_count || '—'}</td>
                  <td className="td-num">{m.pve_count || '—'}</td>
                  <td style={{ maxWidth: 100, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                    {m.mvp || '—'}
                  </td>
                  <td style={{ whiteSpace: 'nowrap', fontSize: 12 }}>
                    <span className="team-a">{ts.a?.kills || 0}</span>
                    {' / '}
                    <span className="team-b">{ts.b?.kills || 0}</span>
                    {' / '}
                    <span className="team-c">{ts.c?.kills || 0}</span>
                    {' / '}
                    <span className="team-d">{ts.d?.kills || 0}</span>
                  </td>
                  <td><button className="btn btn-small btn-view" onClick={e => { e.stopPropagation(); onSelect(m.match_id); }}>View</button></td>
                </tr>
              );
            })}
          </tbody>
        </table>
      )}
    </div>
  );
}
