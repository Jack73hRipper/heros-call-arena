import React, { useMemo } from 'react';

const TEAM_LABELS = { a: 'Team A', b: 'Team B', c: 'Team C', d: 'Team D' };
const TEAM_KEYS = ['a', 'b', 'c', 'd'];

export default function ExplorationInspector({ match, onBack }) {
  if (!match) {
    return (
      <div className="no-match-msg">
        <p>No match selected</p>
        <button className="btn" onClick={onBack}>← Back to Browser</button>
      </div>
    );
  }

  const timeline = match.timeline || [];
  const unitStats = match.unit_stats || {};
  const totalTurns = match.duration_turns || 0;

  // Analyze exploration from timeline events
  const explorationData = useMemo(() => {
    const teamData = {};
    for (const tk of TEAM_KEYS) {
      teamData[tk] = {
        tilesVisited: new Set(),
        doorsOpened: 0,
        chestsOpened: 0,
        moveCount: 0,
        waitCount: 0,
        interactCount: 0,
        uniquePositions: new Set(),
      };
    }

    for (const turnData of timeline) {
      const events = turnData.events || [];
      for (const ev of events) {
        if (ev.type === 'move' && ev.unit) {
          const unit = unitStats[ev.unit];
          const tk = unit?.team;
          if (tk && teamData[tk]) {
            teamData[tk].moveCount++;
            if (ev.to) {
              const key = `${ev.to[0]},${ev.to[1]}`;
              teamData[tk].tilesVisited.add(key);
              teamData[tk].uniquePositions.add(key);
            }
          }
        }
        if (ev.type === 'door') {
          // Try to attribute door to nearest team
          for (const tk of TEAM_KEYS) {
            teamData[tk].doorsOpened += 0.25; // Split credit
          }
        }
        if (ev.type === 'chest' && ev.unit) {
          const unit = unitStats[ev.unit];
          const tk = unit?.team;
          if (tk && teamData[tk]) teamData[tk].chestsOpened++;
        }
      }
    }

    return teamData;
  }, [timeline, unitStats]);

  // Per-team movement pattern analysis — detect potential stalling
  const movementAnalysis = useMemo(() => {
    const analysis = {};
    for (const tk of TEAM_KEYS) {
      const units = Object.entries(unitStats).filter(([_, u]) => u.team === tk);
      let totalDmg = 0, totalHeal = 0, totalKills = 0, totalSurvived = 0;
      for (const [_, u] of units) {
        totalDmg += u.damage_dealt || 0;
        totalHeal += u.healing_done || 0;
        totalKills += u.kills || 0;
        if (u.status === 'survived') totalSurvived++;
      }

      const tileCount = explorationData[tk]?.tilesVisited.size || 0;
      const moveCount = explorationData[tk]?.moveCount || 0;
      const moveEfficiency = moveCount > 0 ? (tileCount / moveCount * 100).toFixed(1) : 0;
      const movesPerTurn = totalTurns > 0 ? (moveCount / totalTurns).toFixed(1) : 0;

      // Heuristic health score
      let score = 100;
      if (tileCount < 20) score -= 20;
      else if (tileCount < 50) score -= 10;
      if (moveEfficiency < 10) score -= 15;
      if (totalKills === 0 && totalTurns > 50) score -= 10;
      if (totalSurvived === 0) score -= 15;
      score = Math.max(0, Math.min(100, score));

      analysis[tk] = {
        units: units.length,
        survived: totalSurvived,
        tileCount,
        moveCount,
        moveEfficiency,
        movesPerTurn,
        totalDmg,
        totalHeal,
        totalKills,
        score,
      };
    }
    return analysis;
  }, [unitStats, explorationData, totalTurns]);

  function healthClass(score) {
    if (score >= 80) return 'health-excellent';
    if (score >= 50) return 'health-good';
    return 'health-poor';
  }

  function healthLabel(score) {
    if (score >= 80) return 'HEALTHY';
    if (score >= 50) return 'MODERATE';
    return 'STALLING';
  }

  return (
    <div className="tab-content">
      <div className="tab-header">
        <h2>Exploration Inspector</h2>
        <div className="header-actions">
          <span style={{ fontFamily: 'monospace', fontSize: 12, color: 'var(--text-dim)' }}>
            {match.match_id?.substring(0, 8)} — {totalTurns} turns
          </span>
          <button className="btn btn-small" onClick={onBack}>← Browser</button>
        </div>
      </div>

      {/* Exploration Overview Cards */}
      <div className="card-grid" style={{ gridTemplateColumns: 'repeat(4, 1fr)' }}>
        {TEAM_KEYS.map(tk => {
          const a = movementAnalysis[tk];
          return (
            <div key={tk} className="card">
              <div className="card-header">
                <span className={`card-label team-${tk}`}>{TEAM_LABELS[tk]}</span>
                <span className={`health-score ${healthClass(a.score)}`} style={{ fontSize: 14, padding: '4px 10px' }}>
                  {a.score}
                </span>
              </div>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '4px 12px', fontSize: 12 }}>
                <div><span style={{ color: 'var(--text-dim)' }}>Tiles:</span> {a.tileCount}</div>
                <div><span style={{ color: 'var(--text-dim)' }}>Moves:</span> {a.moveCount}</div>
                <div><span style={{ color: 'var(--text-dim)' }}>Efficiency:</span> {a.moveEfficiency}%</div>
                <div><span style={{ color: 'var(--text-dim)' }}>Moves/turn:</span> {a.movesPerTurn}</div>
                <div><span style={{ color: 'var(--text-dim)' }}>Alive:</span> {a.survived}/{a.units}</div>
                <div><span style={{ color: 'var(--text-dim)' }}>Kills:</span> {a.totalKills}</div>
              </div>
            </div>
          );
        })}
      </div>

      {/* Tile Coverage Bars */}
      <div className="panel">
        <div className="panel-title">Tile Coverage</div>
        {TEAM_KEYS.map(tk => {
          const a = movementAnalysis[tk];
          const maxTiles = Math.max(...TEAM_KEYS.map(t => movementAnalysis[t].tileCount), 1);
          const pct = (a.tileCount / maxTiles) * 100;
          return (
            <div key={tk} className="stat-row">
              <span className={`stat-label team-${tk}`}>{TEAM_LABELS[tk]}</span>
              <div className="stat-bar-bg">
                <div className={`stat-bar-fill bar-${tk}`} style={{ width: `${pct}%` }} />
                <span className="stat-bar-text">{a.tileCount} tiles</span>
              </div>
            </div>
          );
        })}
      </div>

      {/* Move Efficiency Bars */}
      <div className="two-col">
        <div className="panel">
          <div className="panel-title">Total Moves</div>
          {TEAM_KEYS.map(tk => {
            const a = movementAnalysis[tk];
            const maxMoves = Math.max(...TEAM_KEYS.map(t => movementAnalysis[t].moveCount), 1);
            const pct = (a.moveCount / maxMoves) * 100;
            return (
              <div key={tk} className="stat-row">
                <span className={`stat-label team-${tk}`}>{TEAM_LABELS[tk]}</span>
                <div className="stat-bar-bg">
                  <div className={`stat-bar-fill bar-${tk}`} style={{ width: `${pct}%` }} />
                  <span className="stat-bar-text">{a.moveCount}</span>
                </div>
              </div>
            );
          })}
        </div>

        <div className="panel">
          <div className="panel-title">Move Efficiency (unique tiles / total moves)</div>
          {TEAM_KEYS.map(tk => {
            const a = movementAnalysis[tk];
            const pct = parseFloat(a.moveEfficiency) || 0;
            return (
              <div key={tk} className="stat-row">
                <span className={`stat-label team-${tk}`}>{TEAM_LABELS[tk]}</span>
                <div className="stat-bar-bg">
                  <div className={`stat-bar-fill bar-${tk}`} style={{ width: `${Math.min(pct, 100)}%` }} />
                  <span className="stat-bar-text">{a.moveEfficiency}%</span>
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* Per-Unit Movement Detail */}
      <div className="panel">
        <div className="panel-title">Per-Hero Movement Summary</div>
        <table className="scoreboard">
          <thead>
            <tr>
              <th>Team</th>
              <th>Hero</th>
              <th>Class</th>
              <th>Status</th>
              <th className="td-num">Turns Survived</th>
              <th className="td-num">Damage</th>
              <th className="td-num">Kills</th>
              <th className="td-num">Items Looted</th>
            </tr>
          </thead>
          <tbody>
            {TEAM_KEYS.flatMap(tk =>
              Object.entries(unitStats)
                .filter(([_, u]) => u.team === tk)
                .sort((a, b) => (b[1].damage_dealt || 0) - (a[1].damage_dealt || 0))
                .map(([uid, u]) => (
                  <tr key={uid} className={u.status === 'died' ? 'unit-dead' : ''}>
                    <td><span className={`team-badge badge-${tk}`}>{tk.toUpperCase()}</span></td>
                    <td className="unit-name">{u.username || uid.substring(0, 8)}</td>
                    <td className="unit-class">{u.class_id || '—'}</td>
                    <td>{u.status === 'survived'
                      ? <span style={{ color: 'var(--green)' }}>Alive</span>
                      : <span style={{ color: 'var(--red)' }}>Dead</span>}
                    </td>
                    <td className="td-num">{u.turns_survived || '—'}</td>
                    <td className="td-num">{(u.damage_dealt || 0).toLocaleString()}</td>
                    <td className="td-num">{u.kills || 0}</td>
                    <td className="td-num">{u.items_looted || 0}</td>
                  </tr>
                ))
            )}
          </tbody>
        </table>
      </div>

      {/* Exploration Health Diagnosis */}
      <div className="panel">
        <div className="panel-title">Exploration Health Diagnosis</div>
        <div style={{ display: 'grid', gap: 12 }}>
          {TEAM_KEYS.map(tk => {
            const a = movementAnalysis[tk];
            const issues = [];
            if (a.tileCount < 20) issues.push('Very few unique tiles explored — team may be stuck or stalling');
            if (parseFloat(a.moveEfficiency) < 10) issues.push('Low move efficiency — lots of repeated movement over same tiles');
            if (a.totalKills === 0 && totalTurns > 50) issues.push('No kills after 50+ turns — team may not be engaging enemies');
            if (a.survived === 0) issues.push('Team fully eliminated');

            return (
              <div key={tk} style={{ padding: '8px 12px', background: 'var(--bg-dark)', borderRadius: 4, border: `1px solid var(--border)` }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 4 }}>
                  <span className={`team-${tk}`} style={{ fontWeight: 600 }}>{TEAM_LABELS[tk]}</span>
                  <span className={`health-score ${healthClass(a.score)}`} style={{ fontSize: 12, padding: '2px 8px' }}>
                    {a.score}/100 — {healthLabel(a.score)}
                  </span>
                </div>
                {issues.length === 0 ? (
                  <div style={{ fontSize: 12, color: 'var(--green)' }}>✓ No exploration issues detected</div>
                ) : (
                  issues.map((issue, i) => (
                    <div key={i} style={{ fontSize: 12, color: 'var(--red)', marginTop: 2 }}>⚠ {issue}</div>
                  ))
                )}
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
