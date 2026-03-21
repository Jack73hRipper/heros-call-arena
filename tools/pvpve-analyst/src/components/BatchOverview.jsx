import React, { useState, useEffect, useRef, useCallback } from 'react';

const TEAM_LABELS = { a: 'Team A', b: 'Team B', c: 'Team C', d: 'Team D' };
const TEAM_COLORS_HEX = { a: '#5588cc', b: '#cc5555', c: '#ccaa33', d: '#cc55cc' };
const TEAM_KEYS = ['a', 'b', 'c', 'd'];

export default function BatchOverview() {
  const [data, setData] = useState(null);
  const [classStats, setClassStats] = useState([]);
  const [teamStats, setTeamStats] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const pieRef = useRef(null);

  useEffect(() => {
    async function load() {
      setLoading(true);
      try {
        const [batchRes, classRes, teamRes] = await Promise.all([
          fetch('/api/batch-overview'),
          fetch('/api/class-stats'),
          fetch('/api/team-stats'),
        ]);
        if (!batchRes.ok) throw new Error(`Batch: HTTP ${batchRes.status}`);
        if (!classRes.ok) throw new Error(`Class: HTTP ${classRes.status}`);
        if (!teamRes.ok) throw new Error(`Team: HTTP ${teamRes.status}`);
        setData(await batchRes.json());
        setClassStats(await classRes.json());
        setTeamStats(await teamRes.json());
      } catch (err) {
        setError(err.message);
      } finally {
        setLoading(false);
      }
    }
    load();
  }, []);

  // Draw win rate pie chart
  const drawPie = useCallback(() => {
    if (!data || !pieRef.current) return;
    const canvas = pieRef.current;
    const ctx = canvas.getContext('2d');
    const size = 200;
    canvas.width = size;
    canvas.height = size;
    const cx = size / 2, cy = size / 2, r = 80;

    ctx.clearRect(0, 0, size, size);

    const wc = data.win_counts || {};
    const slices = [
      { key: 'a', val: wc.a || 0, color: TEAM_COLORS_HEX.a },
      { key: 'b', val: wc.b || 0, color: TEAM_COLORS_HEX.b },
      { key: 'c', val: wc.c || 0, color: TEAM_COLORS_HEX.c },
      { key: 'd', val: wc.d || 0, color: TEAM_COLORS_HEX.d },
      { key: 'draw', val: wc.draw || 0, color: '#555566' },
    ];
    const total = slices.reduce((s, sl) => s + sl.val, 0);
    if (total === 0) return;

    let startAngle = -Math.PI / 2;
    for (const sl of slices) {
      if (sl.val === 0) continue;
      const sweep = (sl.val / total) * Math.PI * 2;
      ctx.beginPath();
      ctx.moveTo(cx, cy);
      ctx.arc(cx, cy, r, startAngle, startAngle + sweep);
      ctx.closePath();
      ctx.fillStyle = sl.color;
      ctx.fill();
      ctx.strokeStyle = '#0a0a0e';
      ctx.lineWidth = 2;
      ctx.stroke();

      // Label
      if (sl.val / total > 0.05) {
        const mid = startAngle + sweep / 2;
        const lx = cx + Math.cos(mid) * (r * 0.6);
        const ly = cy + Math.sin(mid) * (r * 0.6);
        ctx.fillStyle = '#e8e8f0';
        ctx.font = 'bold 12px monospace';
        ctx.textAlign = 'center';
        ctx.textBaseline = 'middle';
        ctx.fillText(`${Math.round(sl.val / total * 100)}%`, lx, ly);
      }

      startAngle += sweep;
    }
  }, [data]);

  useEffect(() => { drawPie(); }, [drawPie]);

  if (loading) return <div className="loading">Loading batch data...</div>;
  if (error) return <div className="error-msg">Error: {error}</div>;
  if (!data || data.total_matches === 0) {
    return (
      <div className="empty-state">
        <div className="empty-icon">📊</div>
        <p>No PVPVE matches found</p>
        <p className="hint">Run <code>start-batch-pvpve.bat</code> to generate match data</p>
      </div>
    );
  }

  const wc = data.win_counts || {};

  return (
    <div className="tab-content">
      <div className="tab-header">
        <h2>Batch Overview</h2>
        <span style={{ fontSize: 12, color: 'var(--text-dim)' }}>{data.total_matches} PVPVE matches</span>
      </div>

      {/* Summary Cards */}
      <div className="card-grid">
        <div className="card">
          <div className="card-header"><span className="card-label">Total Matches</span></div>
          <div className="card-value">{data.total_matches}</div>
        </div>
        <div className="card">
          <div className="card-header"><span className="card-label">Avg Turns</span></div>
          <div className="card-value">{data.avg_turns}</div>
        </div>
        <div className="card">
          <div className="card-header"><span className="card-label">Draw Rate</span></div>
          <div className="card-value" style={{ color: (wc.draw / data.total_matches) > 0.3 ? 'var(--red)' : 'var(--text-bright)' }}>
            {data.total_matches > 0 ? Math.round((wc.draw || 0) / data.total_matches * 100) : 0}%
          </div>
        </div>
      </div>

      {/* Win Distribution */}
      <div className="panel">
        <div className="panel-title">Win Distribution</div>
        <div className="pie-container">
          <canvas ref={pieRef} className="pie-canvas" />
          <div className="pie-legend">
            {TEAM_KEYS.map(tk => (
              <div key={tk} className="pie-legend-item">
                <div className="pie-legend-swatch" style={{ background: TEAM_COLORS_HEX[tk] }} />
                <span className={`team-${tk}`}>{TEAM_LABELS[tk]}</span>
                <span style={{ color: 'var(--text-dim)' }}>
                  {wc[tk] || 0} wins ({data.total_matches > 0 ? Math.round((wc[tk] || 0) / data.total_matches * 100) : 0}%)
                </span>
              </div>
            ))}
            <div className="pie-legend-item">
              <div className="pie-legend-swatch" style={{ background: '#555566' }} />
              <span style={{ color: 'var(--text-dim)' }}>Draw</span>
              <span style={{ color: 'var(--text-dim)' }}>
                {wc.draw || 0} ({data.total_matches > 0 ? Math.round((wc.draw || 0) / data.total_matches * 100) : 0}%)
              </span>
            </div>
          </div>
        </div>
      </div>

      {/* Win Rate Bars */}
      <div className="panel">
        <div className="panel-title">Team Win Rates</div>
        {TEAM_KEYS.map(tk => {
          const wins = wc[tk] || 0;
          const pct = data.total_matches > 0 ? (wins / data.total_matches * 100) : 0;
          return (
            <div key={tk} className="stat-row">
              <span className={`stat-label team-${tk}`}>{TEAM_LABELS[tk]}</span>
              <div className="stat-bar-bg">
                <div className={`stat-bar-fill bar-${tk}`} style={{ width: `${pct}%` }} />
                <span className="stat-bar-text">{wins}W ({pct.toFixed(1)}%)</span>
              </div>
            </div>
          );
        })}
      </div>

      {/* Team Aggregate Stats */}
      {teamStats && (
        <div className="panel">
          <div className="panel-title">Team Aggregate Stats (across {teamStats.match_count} matches)</div>
          <table className="scoreboard">
            <thead>
              <tr>
                <th>Team</th>
                <th className="td-num">Wins</th>
                <th className="td-num">Win Rate</th>
                <th className="td-num">Total Damage</th>
                <th className="td-num">Total Healing</th>
                <th className="td-num">Total Kills</th>
                <th className="td-num">Total Deaths</th>
                <th className="td-num">Survival Rate</th>
              </tr>
            </thead>
            <tbody>
              {TEAM_KEYS.map(tk => {
                const t = teamStats.teams?.[tk];
                if (!t) return null;
                const winRate = t.matches > 0 ? (t.wins / t.matches * 100).toFixed(1) : '0.0';
                const survRate = t.total_heroes > 0 ? (t.total_survivors / t.total_heroes * 100).toFixed(1) : '0.0';
                return (
                  <tr key={tk}>
                    <td><span className={`team-badge badge-${tk}`}>{TEAM_LABELS[tk]}</span></td>
                    <td className="td-num">{t.wins}</td>
                    <td className="td-num">{winRate}%</td>
                    <td className="td-num">{(t.total_damage || 0).toLocaleString()}</td>
                    <td className="td-num">{(t.total_healing || 0).toLocaleString()}</td>
                    <td className="td-num">{t.total_kills}</td>
                    <td className="td-num">{t.total_deaths}</td>
                    <td className="td-num">{survRate}%</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      {/* Class Performance Table */}
      {classStats.length > 0 && (
        <div className="panel">
          <div className="panel-title">Class Performance in PVPVE ({classStats.length} classes)</div>
          <table className="scoreboard">
            <thead>
              <tr>
                <th>Class</th>
                <th className="td-num">Appearances</th>
                <th className="td-num">Win Rate</th>
                <th className="td-num">Survival</th>
                <th className="td-num">Avg Damage</th>
                <th className="td-num">Avg Healing</th>
                <th className="td-num">Avg Kills</th>
                <th className="td-num">Avg Deaths</th>
                <th className="td-num">Boss Kills</th>
              </tr>
            </thead>
            <tbody>
              {classStats.map(c => (
                <tr key={c.class_id}>
                  <td style={{ textTransform: 'capitalize', fontWeight: 600 }}>{c.class_id}</td>
                  <td className="td-num">{c.appearances}</td>
                  <td className="td-num" style={{ color: c.win_rate >= 30 ? 'var(--green)' : c.win_rate >= 20 ? 'var(--text)' : 'var(--red)' }}>
                    {c.win_rate}%
                  </td>
                  <td className="td-num" style={{ color: c.survival_rate >= 50 ? 'var(--green)' : 'var(--text-dim)' }}>
                    {c.survival_rate}%
                  </td>
                  <td className="td-num">{c.avg_damage.toLocaleString()}</td>
                  <td className="td-num">{c.avg_healing.toLocaleString()}</td>
                  <td className="td-num">{c.avg_kills}</td>
                  <td className="td-num">{c.avg_deaths}</td>
                  <td className="td-num" style={{ color: c.boss_kills > 0 ? 'var(--gold)' : 'var(--text-dim)' }}>
                    {c.boss_kills}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Daily Activity */}
      {data.daily && data.daily.length > 0 && (
        <div className="panel">
          <div className="panel-title">Daily Match Activity</div>
          <table className="scoreboard">
            <thead>
              <tr>
                <th>Date</th>
                <th className="td-num">Matches</th>
                <th className="td-num">Avg Turns</th>
              </tr>
            </thead>
            <tbody>
              {data.daily.map(d => (
                <tr key={d.date}>
                  <td>{d.date}</td>
                  <td className="td-num">{d.matches}</td>
                  <td className="td-num">{d.avg_turns}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
