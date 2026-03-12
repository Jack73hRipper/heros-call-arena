import React, { useState, useEffect, useMemo } from 'react';

// ── Helpers ────────────────────────────────────────────
const CLASS_COLORS = {
  crusader: '#4a8fd0', confessor: '#f0c040', inquisitor: '#a0a0a0',
  ranger: '#44aa44', hexblade: '#cc44cc', mage: '#5588cc',
  bard: '#e08040', blood_knight: '#cc3333', plague_doctor: '#66cc66',
  revenant: '#8888cc', shaman: '#44cccc',
};

function classColor(c) { return CLASS_COLORS[c] || '#888'; }
function fmtClass(c) { return c ? c.split('_').map(w => w[0].toUpperCase() + w.slice(1)).join(' ') : '—'; }

function WinRateBar({ rate }) {
  const color = rate >= 55 ? 'var(--green)' : rate <= 45 ? 'var(--red)' : 'var(--text-dim)';
  return (
    <div className="winrate-bar-container">
      <div className="winrate-bar-track">
        <div className="winrate-bar-fill" style={{ width: `${rate}%`, backgroundColor: color }} />
        <div className="winrate-bar-mid" />
      </div>
      <span className="winrate-bar-pct" style={{ color }}>{rate}%</span>
    </div>
  );
}

export default function CompAnalysis() {
  const [compStats, setCompStats] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [sortKey, setSortKey] = useState('matches');
  const [sortAsc, setSortAsc] = useState(false);
  const [minMatches, setMinMatches] = useState(1);
  const [sizeFilter, setSizeFilter] = useState('all'); // all, 3, 4, 5, etc.

  useEffect(() => {
    fetchCompStats();
  }, []);

  async function fetchCompStats() {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch('/api/comp-stats');
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      setCompStats(data);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  // Filter & sort
  const filtered = useMemo(() => {
    let arr = compStats.filter(c => c.matches >= minMatches);
    if (sizeFilter !== 'all') {
      const size = parseInt(sizeFilter, 10);
      arr = arr.filter(c => c.classes.length === size);
    }
    arr.sort((a, b) => {
      const va = a[sortKey] ?? 0;
      const vb = b[sortKey] ?? 0;
      return sortAsc ? va - vb : vb - va;
    });
    return arr;
  }, [compStats, sortKey, sortAsc, minMatches, sizeFilter]);

  // Best and worst comps (min 3 matches)
  const rankedComps = useMemo(() => {
    const qualified = compStats.filter(c => c.matches >= 3);
    const sorted = [...qualified].sort((a, b) => b.win_rate - a.win_rate);
    return {
      best: sorted.slice(0, 5),
      worst: sorted.slice(-5).reverse(),
    };
  }, [compStats]);

  // Available team sizes
  const teamSizes = useMemo(() => {
    const sizes = new Set(compStats.map(c => c.classes.length));
    return [...sizes].sort((a, b) => a - b);
  }, [compStats]);

  function handleSort(key) {
    if (sortKey === key) setSortAsc(!sortAsc);
    else { setSortKey(key); setSortAsc(false); }
  }

  function sortIndicator(key) {
    if (sortKey !== key) return '';
    return sortAsc ? ' ▲' : ' ▼';
  }

  return (
    <div className="tab-content comp-analysis">
      <div className="tab-header">
        <h2>Composition Analysis</h2>
        <div className="header-actions">
          <span className="match-count">{filtered.length} compositions</span>
          <button className="btn btn-secondary" onClick={fetchCompStats}>Refresh</button>
        </div>
      </div>

      {loading && <div className="loading">Loading composition stats...</div>}
      {error && <div className="error-msg">Error: {error}</div>}

      {!loading && compStats.length === 0 && (
        <div className="empty-state">
          <div className="empty-icon">🗡️</div>
          <p>No composition data available.</p>
          <p className="hint">Play some matches to generate composition data.</p>
        </div>
      )}

      {/* ── Best & Worst Comps ── */}
      {!loading && rankedComps.best.length > 0 && (
        <div className="comp-rankings">
          <div className="comp-ranking-panel comp-best">
            <h3 className="comp-ranking-title">
              <span className="ranking-icon">▲</span> Best Compositions
              <span className="ranking-note">(min 3 matches)</span>
            </h3>
            {rankedComps.best.map((c, i) => (
              <CompRankCard key={c.comp_key} comp={c} rank={i + 1} type="best" />
            ))}
          </div>
          <div className="comp-ranking-panel comp-worst">
            <h3 className="comp-ranking-title">
              <span className="ranking-icon">▼</span> Worst Compositions
              <span className="ranking-note">(min 3 matches)</span>
            </h3>
            {rankedComps.worst.map((c, i) => (
              <CompRankCard key={c.comp_key} comp={c} rank={i + 1} type="worst" />
            ))}
          </div>
        </div>
      )}

      {/* ── Filters ── */}
      {!loading && compStats.length > 0 && (
        <>
          <div className="section-title">All Compositions</div>
          <div className="filter-bar">
            <div className="filter-group">
              <label className="filter-label">Min Matches</label>
              <select
                className="filter-select"
                value={minMatches}
                onChange={e => setMinMatches(parseInt(e.target.value, 10))}
              >
                <option value={1}>1+</option>
                <option value={2}>2+</option>
                <option value={3}>3+</option>
                <option value={5}>5+</option>
                <option value={10}>10+</option>
              </select>
            </div>
            <div className="filter-group">
              <label className="filter-label">Team Size</label>
              <select
                className="filter-select"
                value={sizeFilter}
                onChange={e => setSizeFilter(e.target.value)}
              >
                <option value="all">All Sizes</option>
                {teamSizes.map(s => (
                  <option key={s} value={s}>{s}-player</option>
                ))}
              </select>
            </div>
          </div>

          {/* ── Comp Table ── */}
          <table className="comp-table">
            <thead>
              <tr>
                <th>Composition</th>
                <th onClick={() => handleSort('matches')} className="sortable">
                  Matches{sortIndicator('matches')}
                </th>
                <th onClick={() => handleSort('win_rate')} className="sortable">
                  Win Rate{sortIndicator('win_rate')}
                </th>
                <th onClick={() => handleSort('wins')} className="sortable">
                  W{sortIndicator('wins')}
                </th>
                <th onClick={() => handleSort('losses')} className="sortable">
                  L{sortIndicator('losses')}
                </th>
                <th>Size</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map(c => (
                <tr key={c.comp_key}>
                  <td>
                    <div className="comp-classes">
                      {c.classes.map((cls, i) => (
                        <span
                          key={i}
                          className="comp-class-tag"
                          style={{ color: classColor(cls), borderColor: classColor(cls) }}
                        >
                          {fmtClass(cls)}
                        </span>
                      ))}
                    </div>
                  </td>
                  <td className="td-num">{c.matches}</td>
                  <td><WinRateBar rate={c.win_rate} /></td>
                  <td className="td-num td-win">{c.wins}</td>
                  <td className="td-num td-loss">{c.losses}</td>
                  <td className="td-num">{c.classes.length}</td>
                </tr>
              ))}
            </tbody>
          </table>

          {filtered.length === 0 && (
            <div className="empty-state">
              <p>No compositions match the current filters.</p>
            </div>
          )}
        </>
      )}
    </div>
  );
}

// ── Comp Rank Card ──
function CompRankCard({ comp, rank, type }) {
  const borderColor = type === 'best' ? 'var(--green)' : 'var(--red)';
  const rateColor = comp.win_rate >= 55 ? 'var(--green)' : comp.win_rate <= 45 ? 'var(--red)' : 'var(--text-dim)';

  return (
    <div className="comp-rank-card" style={{ borderLeftColor: borderColor }}>
      <span className="comp-rank-number">#{rank}</span>
      <div className="comp-rank-body">
        <div className="comp-classes">
          {comp.classes.map((cls, i) => (
            <span
              key={i}
              className="comp-class-tag"
              style={{ color: classColor(cls), borderColor: classColor(cls) }}
            >
              {fmtClass(cls)}
            </span>
          ))}
        </div>
        <div className="comp-rank-stats">
          <span className="comp-rank-rate" style={{ color: rateColor }}>
            {comp.win_rate}%
          </span>
          <span className="comp-rank-record">
            {comp.wins}W – {comp.losses}L ({comp.matches} games)
          </span>
        </div>
      </div>
    </div>
  );
}
