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
        <div
          className="winrate-bar-fill"
          style={{ width: `${rate}%`, backgroundColor: color }}
        />
        <div className="winrate-bar-mid" />
      </div>
      <span className="winrate-bar-pct" style={{ color }}>{rate}%</span>
    </div>
  );
}

export default function ClassBalance() {
  const [classStats, setClassStats] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [sortKey, setSortKey] = useState('win_rate');
  const [sortAsc, setSortAsc] = useState(false);
  const [showMatrix, setShowMatrix] = useState(false);
  const [matrixData, setMatrixData] = useState(null);
  const [matrixLoading, setMatrixLoading] = useState(false);

  useEffect(() => {
    fetchClassStats();
  }, []);

  async function fetchClassStats() {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch('/api/class-stats');
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      setClassStats(data);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  // Fetch all matches for building the class vs class matrix
  async function fetchMatrix() {
    setMatrixLoading(true);
    try {
      const res = await fetch('/api/matches');
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const matchList = await res.json();

      // For each match, fetch full detail to get team rosters
      const matrix = {}; // classA → classB → { wins, losses }

      // We need full reports — fetch them all (may be slow with many matches)
      for (const m of matchList) {
        try {
          const detailRes = await fetch(`/api/matches/${m.match_id}`);
          if (!detailRes.ok) continue;
          const report = await detailRes.json();

          if (!report.teams || !report.winner) continue;

          const teamAClasses = (report.teams.team_a || []).map(u => u.class_id).filter(Boolean);
          const teamBClasses = (report.teams.team_b || []).map(u => u.class_id).filter(Boolean);
          const aWon = report.winner === 'team_a';
          const bWon = report.winner === 'team_b';

          // For each class on team A vs each class on team B
          for (const ca of teamAClasses) {
            for (const cb of teamBClasses) {
              if (!matrix[ca]) matrix[ca] = {};
              if (!matrix[ca][cb]) matrix[ca][cb] = { wins: 0, losses: 0 };
              if (aWon) matrix[ca][cb].wins++;
              if (bWon) matrix[ca][cb].losses++;

              if (!matrix[cb]) matrix[cb] = {};
              if (!matrix[cb][ca]) matrix[cb][ca] = { wins: 0, losses: 0 };
              if (bWon) matrix[cb][ca].wins++;
              if (aWon) matrix[cb][ca].losses++;
            }
          }
        } catch { continue; }
      }

      setMatrixData(matrix);
    } catch (err) {
      setError(err.message);
    } finally {
      setMatrixLoading(false);
    }
  }

  // Sorting
  const sorted = useMemo(() => {
    const arr = [...classStats];
    arr.sort((a, b) => {
      const va = a[sortKey] ?? 0;
      const vb = b[sortKey] ?? 0;
      if (typeof va === 'string') return sortAsc ? va.localeCompare(vb) : vb.localeCompare(va);
      return sortAsc ? va - vb : vb - va;
    });
    return arr;
  }, [classStats, sortKey, sortAsc]);

  function handleSort(key) {
    if (sortKey === key) {
      setSortAsc(!sortAsc);
    } else {
      setSortKey(key);
      setSortAsc(false);
    }
  }

  function sortIndicator(key) {
    if (sortKey !== key) return '';
    return sortAsc ? ' ▲' : ' ▼';
  }

  // ── Stat bar heights (vertical bars in avg stats) ──
  const maxAvgDmg  = Math.max(1, ...classStats.map(c => c.avg_damage || 0));
  const maxAvgHeal = Math.max(1, ...classStats.map(c => c.avg_healing || 0));
  const maxAvgK    = Math.max(1, ...classStats.map(c => c.avg_kills || 0));
  const maxAvgD    = Math.max(1, ...classStats.map(c => c.avg_deaths || 0));

  // Matrix classes list
  const matrixClasses = matrixData ? Object.keys(matrixData).sort() : [];

  function toggleMatrix() {
    if (!showMatrix && !matrixData) {
      fetchMatrix();
    }
    setShowMatrix(!showMatrix);
  }

  return (
    <div className="tab-content class-balance">
      <div className="tab-header">
        <h2>Class Balance</h2>
        <div className="header-actions">
          <button className="btn btn-secondary" onClick={fetchClassStats}>Refresh</button>
        </div>
      </div>

      {loading && <div className="loading">Loading class stats...</div>}
      {error && <div className="error-msg">Error: {error}</div>}

      {!loading && classStats.length === 0 && (
        <div className="empty-state">
          <div className="empty-icon">⚔️</div>
          <p>No class data available.</p>
          <p className="hint">Play some matches to generate balance data.</p>
        </div>
      )}

      {/* ── Win Rate Table ── */}
      {!loading && sorted.length > 0 && (
        <>
          <div className="section-title">Win Rates & Averages</div>
          <table className="class-table">
            <thead>
              <tr>
                <th onClick={() => handleSort('class_id')} className="sortable">Class{sortIndicator('class_id')}</th>
                <th onClick={() => handleSort('appearances')} className="sortable">Games{sortIndicator('appearances')}</th>
                <th onClick={() => handleSort('win_rate')} className="sortable">Win Rate{sortIndicator('win_rate')}</th>
                <th onClick={() => handleSort('wins')} className="sortable">W{sortIndicator('wins')}</th>
                <th onClick={() => handleSort('losses')} className="sortable">L{sortIndicator('losses')}</th>
                <th onClick={() => handleSort('avg_damage')} className="sortable">Avg Dmg{sortIndicator('avg_damage')}</th>
                <th onClick={() => handleSort('avg_healing')} className="sortable">Avg Heal{sortIndicator('avg_healing')}</th>
                <th onClick={() => handleSort('avg_kills')} className="sortable">Avg Kills{sortIndicator('avg_kills')}</th>
                <th onClick={() => handleSort('avg_deaths')} className="sortable">Avg Deaths{sortIndicator('avg_deaths')}</th>
              </tr>
            </thead>
            <tbody>
              {sorted.map(c => (
                <tr key={c.class_id}>
                  <td>
                    <span className="class-tag" style={{ color: classColor(c.class_id) }}>
                      {fmtClass(c.class_id)}
                    </span>
                  </td>
                  <td className="td-num">{c.appearances}</td>
                  <td><WinRateBar rate={c.win_rate} /></td>
                  <td className="td-num td-win">{c.wins}</td>
                  <td className="td-num td-loss">{c.losses}</td>
                  <td className="td-num">{c.avg_damage}</td>
                  <td className="td-num">{c.avg_healing}</td>
                  <td className="td-num">{c.avg_kills}</td>
                  <td className="td-num">{c.avg_deaths}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </>
      )}

      {/* ── Stat Averages Visual Chart ── */}
      {!loading && sorted.length > 0 && (
        <>
          <div className="section-title">Stat Averages Comparison</div>
          <div className="stat-charts">
            <StatChart title="Avg Damage" stats={sorted} field="avg_damage" max={maxAvgDmg} color="var(--red)" />
            <StatChart title="Avg Healing" stats={sorted} field="avg_healing" max={maxAvgHeal} color="var(--green)" />
            <StatChart title="Avg Kills" stats={sorted} field="avg_kills" max={maxAvgK} color="var(--gold)" />
            <StatChart title="Avg Deaths" stats={sorted} field="avg_deaths" max={maxAvgD} color="var(--purple)" />
          </div>
        </>
      )}

      {/* ── Class vs Class Matrix ── */}
      {!loading && sorted.length > 0 && (
        <>
          <div className="section-title matrix-toggle-section">
            <span>Class vs Class Matrix</span>
            <button className="btn btn-small" onClick={toggleMatrix}>
              {showMatrix ? 'Hide' : 'Show'}
            </button>
          </div>

          {showMatrix && matrixLoading && <div className="loading">Building matrix...</div>}

          {showMatrix && matrixData && matrixClasses.length > 0 && (
            <div className="matrix-scroll">
              <table className="matrix-table">
                <thead>
                  <tr>
                    <th className="matrix-corner">vs</th>
                    {matrixClasses.map(c => (
                      <th key={c} className="matrix-header" style={{ color: classColor(c) }}>
                        {fmtClass(c)}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {matrixClasses.map(rowClass => (
                    <tr key={rowClass}>
                      <td className="matrix-row-label" style={{ color: classColor(rowClass) }}>
                        {fmtClass(rowClass)}
                      </td>
                      {matrixClasses.map(colClass => {
                        if (rowClass === colClass) {
                          return <td key={colClass} className="matrix-cell matrix-self">—</td>;
                        }
                        const data = matrixData[rowClass]?.[colClass];
                        if (!data || (data.wins + data.losses === 0)) {
                          return <td key={colClass} className="matrix-cell matrix-empty">·</td>;
                        }
                        const wr = Math.round((data.wins / (data.wins + data.losses)) * 100);
                        const bg = wr >= 55 ? 'rgba(68, 170, 68, 0.2)'
                                 : wr <= 45 ? 'rgba(204, 68, 68, 0.2)'
                                 : 'transparent';
                        const fg = wr >= 55 ? 'var(--green)' : wr <= 45 ? 'var(--red)' : 'var(--text-dim)';
                        return (
                          <td key={colClass} className="matrix-cell" style={{ background: bg, color: fg }}>
                            {wr}%
                            <span className="matrix-record">{data.wins}W-{data.losses}L</span>
                          </td>
                        );
                      })}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          {showMatrix && matrixData && matrixClasses.length === 0 && (
            <div className="empty-state"><p>Not enough data for the matrix.</p></div>
          )}
        </>
      )}
    </div>
  );
}

// ── Stat Chart (horizontal bars per class) ──
function StatChart({ title, stats, field, max, color }) {
  return (
    <div className="stat-chart">
      <h4 className="stat-chart-title">{title}</h4>
      {stats.map(c => {
        const val = c[field] || 0;
        const pct = max > 0 ? (val / max) * 100 : 0;
        return (
          <div key={c.class_id} className="stat-chart-row">
            <span className="stat-chart-class" style={{ color: classColor(c.class_id) }}>
              {fmtClass(c.class_id)}
            </span>
            <div className="stat-chart-track">
              <div className="stat-chart-fill" style={{ width: `${pct}%`, backgroundColor: color }} />
            </div>
            <span className="stat-chart-val">{val}</span>
          </div>
        );
      })}
    </div>
  );
}
