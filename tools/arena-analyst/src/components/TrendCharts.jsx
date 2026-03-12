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

export default function TrendCharts() {
  const [trends, setTrends] = useState([]);
  const [classStats, setClassStats] = useState([]);
  const [allMatches, setAllMatches] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    fetchAll();
  }, []);

  async function fetchAll() {
    setLoading(true);
    setError(null);
    try {
      const [trendsRes, classRes, matchRes] = await Promise.all([
        fetch('/api/trends'),
        fetch('/api/class-stats'),
        fetch('/api/matches'),
      ]);
      if (!trendsRes.ok) throw new Error(`Trends: HTTP ${trendsRes.status}`);
      if (!classRes.ok) throw new Error(`Class stats: HTTP ${classRes.status}`);
      if (!matchRes.ok) throw new Error(`Matches: HTTP ${matchRes.status}`);

      setTrends(await trendsRes.json());
      setClassStats(await classRes.json());
      setAllMatches(await matchRes.json());
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  // ── Match Volume Chart Data ──
  const volumeData = useMemo(() => {
    if (!trends.length) return null;
    const maxMatches = Math.max(1, ...trends.map(t => t.matches));
    return { days: trends, maxMatches };
  }, [trends]);

  // ── Average Match Length Chart Data ──
  const matchLengthData = useMemo(() => {
    if (!trends.length) return null;
    const maxTurns = Math.max(1, ...trends.map(t => t.avg_turns || 0));
    return { days: trends, maxTurns };
  }, [trends]);

  // ── Damage Creep Chart Data ──
  const damageCreepData = useMemo(() => {
    if (!trends.length) return null;
    const maxDmg = Math.max(1, ...trends.map(t => t.avg_damage || 0));
    return { days: trends, maxDmg };
  }, [trends]);

  // ── Win Rate Drift (class win rates per day) ──
  const winRateDrift = useMemo(() => {
    if (!allMatches.length) return null;

    // Group matches by date
    const byDate = {};
    for (const m of allMatches) {
      if (!m.timestamp) continue;
      const dateStr = m.timestamp.substring(0, 10);
      if (!byDate[dateStr]) byDate[dateStr] = [];
      byDate[dateStr].push(m);
    }

    // We need full match details to compute class win rates per day.
    // Since we only have summaries, we'll compute team_a/team_b win records per day
    // For now we display day-level win distribution (team_a vs team_b)
    const dates = Object.keys(byDate).sort();
    return { dates, byDate };
  }, [allMatches]);

  // ── Overall stats summary ──
  const summary = useMemo(() => {
    if (!trends.length) return null;
    const totalMatches = trends.reduce((s, t) => s + t.matches, 0);
    const totalDays = trends.length;
    const avgPerDay = totalMatches > 0 ? (totalMatches / totalDays).toFixed(1) : 0;
    const overallAvgTurns = trends.reduce((s, t) => s + (t.avg_turns || 0), 0) / (totalDays || 1);
    const overallAvgDmg = trends.reduce((s, t) => s + (t.avg_damage || 0), 0) / (totalDays || 1);
    return { totalMatches, totalDays, avgPerDay, overallAvgTurns: Math.round(overallAvgTurns), overallAvgDmg: Math.round(overallAvgDmg) };
  }, [trends]);

  return (
    <div className="tab-content trend-charts">
      <div className="tab-header">
        <h2>Trend Charts</h2>
        <div className="header-actions">
          <button className="btn btn-secondary" onClick={fetchAll}>Refresh</button>
        </div>
      </div>

      {loading && <div className="loading">Loading trend data...</div>}
      {error && <div className="error-msg">Error: {error}</div>}

      {!loading && trends.length === 0 && (
        <div className="empty-state">
          <div className="empty-icon">📈</div>
          <p>No trend data available.</p>
          <p className="hint">Play matches on multiple days to see trends emerge.</p>
        </div>
      )}

      {/* ── Summary Cards ── */}
      {summary && (
        <div className="trend-summary">
          <SummaryCard label="Total Matches" value={summary.totalMatches} icon="⚔" />
          <SummaryCard label="Active Days" value={summary.totalDays} icon="📅" />
          <SummaryCard label="Avg / Day" value={summary.avgPerDay} icon="📊" />
          <SummaryCard label="Avg Turns" value={summary.overallAvgTurns} icon="⏱" />
          <SummaryCard label="Avg Damage" value={summary.overallAvgDmg.toLocaleString()} icon="💥" />
        </div>
      )}

      {/* ── Match Volume Chart ── */}
      {volumeData && (
        <div className="trend-section">
          <div className="section-title">Match Volume Per Day</div>
          <div className="trend-bar-chart">
            {volumeData.days.map(day => (
              <div key={day.date} className="trend-bar-col" title={`${day.date}: ${day.matches} match${day.matches !== 1 ? 'es' : ''}`}>
                <div className="trend-bar-value">{day.matches}</div>
                <div
                  className="trend-bar"
                  style={{
                    height: `${(day.matches / volumeData.maxMatches) * 100}%`,
                    backgroundColor: 'var(--accent-light)',
                  }}
                />
                <div className="trend-bar-label">{formatDateShort(day.date)}</div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* ── Average Match Length ── */}
      {matchLengthData && (
        <div className="trend-section">
          <div className="section-title">Average Match Length (Turns)</div>
          <div className="trend-line-chart">
            <svg viewBox={`0 0 ${matchLengthData.days.length * 2} 100`} preserveAspectRatio="none" className="trend-svg">
              {/* Grid lines */}
              <line x1="0" y1="25" x2={matchLengthData.days.length * 2} y2="25" stroke="var(--border)" strokeWidth="0.3" vectorEffect="non-scaling-stroke" />
              <line x1="0" y1="50" x2={matchLengthData.days.length * 2} y2="50" stroke="var(--border)" strokeWidth="0.3" vectorEffect="non-scaling-stroke" />
              <line x1="0" y1="75" x2={matchLengthData.days.length * 2} y2="75" stroke="var(--border)" strokeWidth="0.3" vectorEffect="non-scaling-stroke" />
              {/* Area fill */}
              <polygon
                points={`0,100 ${matchLengthData.days.map((d, i) =>
                  `${i * 2},${100 - ((d.avg_turns || 0) / matchLengthData.maxTurns) * 90}`
                ).join(' ')} ${(matchLengthData.days.length - 1) * 2},100`}
                fill="rgba(85, 136, 204, 0.15)"
              />
              {/* Line */}
              <polyline
                points={matchLengthData.days.map((d, i) =>
                  `${i * 2},${100 - ((d.avg_turns || 0) / matchLengthData.maxTurns) * 90}`
                ).join(' ')}
                fill="none"
                stroke="var(--blue)"
                strokeWidth="1.5"
                vectorEffect="non-scaling-stroke"
              />
              {/* Dots */}
              {matchLengthData.days.map((d, i) => (
                <circle
                  key={i}
                  cx={i * 2}
                  cy={100 - ((d.avg_turns || 0) / matchLengthData.maxTurns) * 90}
                  r="0.3"
                  fill="var(--blue)"
                />
              ))}
            </svg>
            <div className="trend-line-axis">
              {matchLengthData.days.map(d => (
                <span key={d.date} className="trend-axis-label" title={d.date}>{formatDateShort(d.date)}</span>
              ))}
            </div>
            <div className="trend-line-values">
              {matchLengthData.days.map(d => (
                <span key={d.date} className="trend-axis-val">{d.avg_turns || 0}</span>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* ── Damage Creep ── */}
      {damageCreepData && (
        <div className="trend-section">
          <div className="section-title">Average Total Damage Per Match (Damage Creep)</div>
          <div className="trend-line-chart">
            <svg viewBox={`0 0 ${damageCreepData.days.length * 2} 100`} preserveAspectRatio="none" className="trend-svg">
              <line x1="0" y1="25" x2={damageCreepData.days.length * 2} y2="25" stroke="var(--border)" strokeWidth="0.3" vectorEffect="non-scaling-stroke" />
              <line x1="0" y1="50" x2={damageCreepData.days.length * 2} y2="50" stroke="var(--border)" strokeWidth="0.3" vectorEffect="non-scaling-stroke" />
              <line x1="0" y1="75" x2={damageCreepData.days.length * 2} y2="75" stroke="var(--border)" strokeWidth="0.3" vectorEffect="non-scaling-stroke" />
              <polygon
                points={`0,100 ${damageCreepData.days.map((d, i) =>
                  `${i * 2},${100 - ((d.avg_damage || 0) / damageCreepData.maxDmg) * 90}`
                ).join(' ')} ${(damageCreepData.days.length - 1) * 2},100`}
                fill="rgba(204, 68, 68, 0.15)"
              />
              <polyline
                points={damageCreepData.days.map((d, i) =>
                  `${i * 2},${100 - ((d.avg_damage || 0) / damageCreepData.maxDmg) * 90}`
                ).join(' ')}
                fill="none"
                stroke="var(--red)"
                strokeWidth="1.5"
                vectorEffect="non-scaling-stroke"
              />
              {damageCreepData.days.map((d, i) => (
                <circle
                  key={i}
                  cx={i * 2}
                  cy={100 - ((d.avg_damage || 0) / damageCreepData.maxDmg) * 90}
                  r="0.3"
                  fill="var(--red)"
                />
              ))}
            </svg>
            <div className="trend-line-axis">
              {damageCreepData.days.map(d => (
                <span key={d.date} className="trend-axis-label" title={d.date}>{formatDateShort(d.date)}</span>
              ))}
            </div>
            <div className="trend-line-values">
              {damageCreepData.days.map(d => (
                <span key={d.date} className="trend-axis-val">{(d.avg_damage || 0).toLocaleString()}</span>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* ── Win Rate Distribution Per Day ── */}
      {winRateDrift && winRateDrift.dates.length > 0 && (
        <div className="trend-section">
          <div className="section-title">Win Rate Distribution Per Day</div>
          <div className="trend-bar-chart trend-stacked">
            {winRateDrift.dates.map(date => {
              const matches = winRateDrift.byDate[date];
              const aWins = matches.filter(m => m.winner === 'team_a').length;
              const bWins = matches.filter(m => m.winner === 'team_b').length;
              const draws = matches.filter(m => m.winner === 'draw' || m.winner === 'party_wipe').length;
              const total = matches.length;
              const aPct = total > 0 ? (aWins / total) * 100 : 0;
              const bPct = total > 0 ? (bWins / total) * 100 : 0;

              return (
                <div key={date} className="trend-stacked-col" title={`${date}: A ${aWins}W / B ${bWins}W / ${draws} draw${draws !== 1 ? 's' : ''}`}>
                  <div className="trend-stacked-bar">
                    <div className="stacked-segment stacked-a" style={{ height: `${aPct}%` }} />
                    <div className="stacked-segment stacked-b" style={{ height: `${bPct}%` }} />
                    {draws > 0 && (
                      <div className="stacked-segment stacked-draw" style={{ height: `${100 - aPct - bPct}%` }} />
                    )}
                  </div>
                  <div className="trend-bar-label">{formatDateShort(date)}</div>
                </div>
              );
            })}
          </div>
          <div className="trend-legend">
            <span className="legend-item"><span className="legend-swatch" style={{ backgroundColor: 'var(--team-a)' }} /> Team A Wins</span>
            <span className="legend-item"><span className="legend-swatch" style={{ backgroundColor: 'var(--team-b)' }} /> Team B Wins</span>
            <span className="legend-item"><span className="legend-swatch" style={{ backgroundColor: 'var(--text-dim)' }} /> Draw / Wipe</span>
          </div>
        </div>
      )}

      {/* ── Class Win Rate Summary ── */}
      {classStats.length > 0 && (
        <div className="trend-section">
          <div className="section-title">Current Class Win Rates</div>
          <div className="trend-class-bars">
            {classStats.map(c => {
              const barWidth = Math.max(2, c.win_rate);
              const color = c.win_rate >= 55 ? 'var(--green)' : c.win_rate <= 45 ? 'var(--red)' : 'var(--text-dim)';
              return (
                <div key={c.class_id} className="trend-class-row">
                  <span className="trend-class-name" style={{ color: classColor(c.class_id) }}>
                    {fmtClass(c.class_id)}
                  </span>
                  <div className="trend-class-track">
                    <div className="trend-class-fill" style={{ width: `${barWidth}%`, backgroundColor: color }} />
                    <div className="trend-class-mid" />
                  </div>
                  <span className="trend-class-pct" style={{ color }}>{c.win_rate}%</span>
                  <span className="trend-class-record">{c.wins}W-{c.losses}L</span>
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}

// ── Summary Card ──
function SummaryCard({ label, value, icon }) {
  return (
    <div className="summary-card">
      <span className="summary-icon">{icon}</span>
      <div className="summary-body">
        <span className="summary-value">{value}</span>
        <span className="summary-label">{label}</span>
      </div>
    </div>
  );
}

// ── Date format helper ──
function formatDateShort(dateStr) {
  const d = new Date(dateStr + 'T00:00:00');
  const month = d.toLocaleString('default', { month: 'short' });
  return `${month} ${d.getDate()}`;
}
