import React, { useState, useEffect, useRef, useCallback, useMemo } from 'react';

const TEAM_COLORS = {
  a: '#5588cc', b: '#cc5555', c: '#ccaa33', d: '#cc55cc', pve: '#888899',
};
const TEAM_LABELS = { a: 'Team A', b: 'Team B', c: 'Team C', d: 'Team D' };
const TEAM_KEYS = ['a', 'b', 'c', 'd'];

export default function CombatTimeline({ match, onBack }) {
  const canvasRef = useRef(null);
  const [turnRange, setTurnRange] = useState([0, 0]);
  const [viewStart, setViewStart] = useState(0);
  const [hoverTurn, setHoverTurn] = useState(null);

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
  const totalTurns = match.duration_turns || timeline.length;

  // Build per-turn survival counts and damage totals per team
  const chartData = useMemo(() => {
    // Track alive units per team across turns
    const aliveByTeam = {};
    for (const tk of TEAM_KEYS) {
      aliveByTeam[tk] = [];
    }
    const dmgByTeam = { a: [], b: [], c: [], d: [] };
    const healByTeam = { a: [], b: [], c: [], d: [] };
    const deathEvents = [];
    const killEvents = [];

    // Initial alive counts
    const currentAlive = {};
    for (const tk of TEAM_KEYS) {
      currentAlive[tk] = Object.values(unitStats).filter(u => u.team === tk).length;
    }

    for (const turnData of timeline) {
      const turn = turnData.turn;
      const events = turnData.events || [];

      // Per-turn accumulators
      const turnDmg = { a: 0, b: 0, c: 0, d: 0 };
      const turnHeal = { a: 0, b: 0, c: 0, d: 0 };

      for (const ev of events) {
        if (ev.type === 'damage' && ev.src) {
          // Find source unit's team
          const srcUnit = unitStats[ev.src];
          const srcTeam = srcUnit?.team;
          if (srcTeam && turnDmg[srcTeam] !== undefined) {
            turnDmg[srcTeam] += ev.dmg || 0;
          }
        }
        if (ev.type === 'heal' && ev.src) {
          const srcUnit = unitStats[ev.src];
          const srcTeam = srcUnit?.team;
          if (srcTeam && turnHeal[srcTeam] !== undefined) {
            turnHeal[srcTeam] += ev.amt || 0;
          }
        }
        if (ev.type === 'death') {
          const deadUnit = unitStats[ev.unit];
          const deadTeam = deadUnit?.team;
          if (deadTeam && currentAlive[deadTeam] !== undefined) {
            currentAlive[deadTeam] = Math.max(0, currentAlive[deadTeam] - 1);
          }
          deathEvents.push({
            turn,
            unit: deadUnit?.username || ev.unit?.substring(0, 8),
            team: deadTeam,
            killer: ev.killer,
          });
        }
      }

      for (const tk of TEAM_KEYS) {
        aliveByTeam[tk].push(currentAlive[tk]);
        dmgByTeam[tk].push(turnDmg[tk]);
        healByTeam[tk].push(turnHeal[tk]);
      }
    }

    return { aliveByTeam, dmgByTeam, healByTeam, deathEvents };
  }, [timeline, unitStats]);

  // Draw survival chart on canvas
  const drawChart = useCallback(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    const w = canvas.width = canvas.parentElement.clientWidth;
    const h = canvas.height = 280;
    const pad = { top: 20, right: 20, bottom: 30, left: 40 };
    const cw = w - pad.left - pad.right;
    const ch = h - pad.top - pad.bottom;

    ctx.clearRect(0, 0, w, h);
    ctx.fillStyle = '#12121a';
    ctx.fillRect(0, 0, w, h);

    const maxAlive = Math.max(
      ...TEAM_KEYS.map(tk => Math.max(...(chartData.aliveByTeam[tk] || [0]), 0)),
      1
    );
    const numTurns = timeline.length || 1;

    // Grid lines
    ctx.strokeStyle = '#2f2f3d';
    ctx.lineWidth = 1;
    for (let i = 0; i <= 5; i++) {
      const y = pad.top + (ch / 5) * i;
      ctx.beginPath();
      ctx.moveTo(pad.left, y);
      ctx.lineTo(w - pad.right, y);
      ctx.stroke();
    }

    // Y-axis labels
    ctx.fillStyle = '#7a7a8e';
    ctx.font = '10px monospace';
    ctx.textAlign = 'right';
    for (let i = 0; i <= 5; i++) {
      const y = pad.top + (ch / 5) * i;
      const val = Math.round(maxAlive * (1 - i / 5));
      ctx.fillText(val, pad.left - 6, y + 4);
    }

    // X-axis labels
    ctx.textAlign = 'center';
    const xStep = Math.max(1, Math.floor(numTurns / 10));
    for (let t = 0; t < numTurns; t += xStep) {
      const x = pad.left + (t / numTurns) * cw;
      ctx.fillText(`T${t + 1}`, x, h - 6);
    }

    // Draw survival lines per team
    for (const tk of TEAM_KEYS) {
      const data = chartData.aliveByTeam[tk];
      if (!data || data.length === 0) continue;
      ctx.strokeStyle = TEAM_COLORS[tk];
      ctx.lineWidth = 2;
      ctx.beginPath();
      for (let i = 0; i < data.length; i++) {
        const x = pad.left + (i / numTurns) * cw;
        const y = pad.top + ch - (data[i] / maxAlive) * ch;
        if (i === 0) ctx.moveTo(x, y);
        else ctx.lineTo(x, y);
      }
      ctx.stroke();
    }

    // Death markers
    for (const d of chartData.deathEvents) {
      const x = pad.left + ((d.turn - 1) / numTurns) * cw;
      const teamColor = TEAM_COLORS[d.team] || '#888';
      ctx.fillStyle = teamColor;
      ctx.beginPath();
      ctx.arc(x, pad.top + ch - 5, 3, 0, Math.PI * 2);
      ctx.fill();
    }

    // Hover line
    if (hoverTurn !== null) {
      const x = pad.left + (hoverTurn / numTurns) * cw;
      ctx.strokeStyle = 'rgba(218, 165, 32, 0.5)';
      ctx.lineWidth = 1;
      ctx.setLineDash([4, 4]);
      ctx.beginPath();
      ctx.moveTo(x, pad.top);
      ctx.lineTo(x, pad.top + ch);
      ctx.stroke();
      ctx.setLineDash([]);
    }

    // Title
    ctx.fillStyle = '#e8e8f0';
    ctx.font = 'bold 12px monospace';
    ctx.textAlign = 'left';
    ctx.fillText('Team Survival Over Time', pad.left, 14);

    // Legend
    let lx = w - pad.right - 280;
    for (const tk of TEAM_KEYS) {
      ctx.fillStyle = TEAM_COLORS[tk];
      ctx.fillRect(lx, 4, 12, 12);
      ctx.fillStyle = '#c8c8d4';
      ctx.font = '11px monospace';
      ctx.fillText(TEAM_LABELS[tk], lx + 16, 14);
      lx += 70;
    }
  }, [chartData, timeline, hoverTurn]);

  useEffect(() => { drawChart(); }, [drawChart]);
  useEffect(() => {
    const handleResize = () => drawChart();
    window.addEventListener('resize', handleResize);
    return () => window.removeEventListener('resize', handleResize);
  }, [drawChart]);

  // Damage chart
  const dmgCanvasRef = useRef(null);
  const drawDmgChart = useCallback(() => {
    const canvas = dmgCanvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    const w = canvas.width = canvas.parentElement.clientWidth;
    const h = canvas.height = 200;
    const pad = { top: 20, right: 20, bottom: 30, left: 50 };
    const cw = w - pad.left - pad.right;
    const ch = h - pad.top - pad.bottom;

    ctx.clearRect(0, 0, w, h);
    ctx.fillStyle = '#12121a';
    ctx.fillRect(0, 0, w, h);

    const numTurns = timeline.length || 1;

    // Compute cumulative damage
    const cumDmg = {};
    for (const tk of TEAM_KEYS) {
      cumDmg[tk] = [];
      let total = 0;
      for (const v of (chartData.dmgByTeam[tk] || [])) {
        total += v;
        cumDmg[tk].push(total);
      }
    }

    const maxDmg = Math.max(...TEAM_KEYS.flatMap(tk => cumDmg[tk] || [0]), 1);

    // Grid
    ctx.strokeStyle = '#2f2f3d';
    ctx.lineWidth = 1;
    for (let i = 0; i <= 4; i++) {
      const y = pad.top + (ch / 4) * i;
      ctx.beginPath();
      ctx.moveTo(pad.left, y);
      ctx.lineTo(w - pad.right, y);
      ctx.stroke();
      ctx.fillStyle = '#7a7a8e';
      ctx.font = '10px monospace';
      ctx.textAlign = 'right';
      const val = Math.round(maxDmg * (1 - i / 4));
      ctx.fillText(val.toLocaleString(), pad.left - 6, y + 4);
    }

    // Lines
    for (const tk of TEAM_KEYS) {
      const data = cumDmg[tk];
      if (!data || data.length === 0) continue;
      ctx.strokeStyle = TEAM_COLORS[tk];
      ctx.lineWidth = 2;
      ctx.beginPath();
      for (let i = 0; i < data.length; i++) {
        const x = pad.left + (i / numTurns) * cw;
        const y = pad.top + ch - (data[i] / maxDmg) * ch;
        if (i === 0) ctx.moveTo(x, y);
        else ctx.lineTo(x, y);
      }
      ctx.stroke();
    }

    ctx.fillStyle = '#e8e8f0';
    ctx.font = 'bold 12px monospace';
    ctx.textAlign = 'left';
    ctx.fillText('Cumulative Damage Over Time', pad.left, 14);
  }, [chartData, timeline]);

  useEffect(() => { drawDmgChart(); }, [drawDmgChart]);
  useEffect(() => {
    const handleResize = () => drawDmgChart();
    window.addEventListener('resize', handleResize);
    return () => window.removeEventListener('resize', handleResize);
  }, [drawDmgChart]);

  // Death event log
  const deathLog = chartData.deathEvents;

  return (
    <div className="tab-content">
      <div className="tab-header">
        <h2>Combat Timeline</h2>
        <div className="header-actions">
          <span style={{ fontFamily: 'monospace', fontSize: 12, color: 'var(--text-dim)' }}>
            {match.match_id?.substring(0, 8)} — {totalTurns} turns
          </span>
          <button className="btn btn-small" onClick={onBack}>← Browser</button>
        </div>
      </div>

      {/* Survival Chart */}
      <div className="panel">
        <div className="timeline-chart">
          <canvas ref={canvasRef} className="timeline-canvas" />
        </div>
      </div>

      {/* Damage Chart */}
      <div className="panel">
        <div className="timeline-chart" style={{ height: 220 }}>
          <canvas ref={dmgCanvasRef} className="timeline-canvas" />
        </div>
      </div>

      {/* Death Log */}
      <div className="two-col">
        <div className="panel">
          <div className="panel-title">Kill Feed ({deathLog.length} deaths)</div>
          <div className="event-log">
            {deathLog.length === 0 ? (
              <div style={{ padding: 20, textAlign: 'center', color: 'var(--text-dim)' }}>No deaths recorded</div>
            ) : (
              deathLog.map((d, i) => {
                const killerUnit = unitStats[d.killer];
                const killerName = killerUnit?.username || d.killer?.substring(0, 8) || '?';
                const killerTeam = killerUnit?.team;
                return (
                  <div key={i} className="event-item">
                    <span className="event-turn">T{d.turn}</span>
                    <span className="event-icon">☠</span>
                    <span className="event-text">
                      <span className={`team-${killerTeam}`}>{killerName}</span>
                      {' killed '}
                      <span className={`team-${d.team}`}>{d.unit}</span>
                    </span>
                  </div>
                );
              })
            )}
          </div>
        </div>

        {/* Per-Turn Damage Breakdown */}
        <div className="panel">
          <div className="panel-title">Damage Per Turn (Top 20 Turns)</div>
          <div className="event-log">
            {(() => {
              // Find turns with highest total damage
              const turnDmg = timeline.map((td, i) => {
                let total = 0;
                for (const ev of (td.events || [])) {
                  if (ev.type === 'damage') total += ev.dmg || 0;
                }
                return { turn: td.turn || i + 1, total };
              }).filter(t => t.total > 0).sort((a, b) => b.total - a.total).slice(0, 20);

              return turnDmg.map((t, i) => (
                <div key={i} className="event-item">
                  <span className="event-turn">T{t.turn}</span>
                  <span className="event-icon">⚔</span>
                  <span className="event-text">{t.total.toLocaleString()} total damage</span>
                </div>
              ));
            })()}
          </div>
        </div>
      </div>
    </div>
  );
}
