import React, { useMemo } from 'react';

// ── Helpers ────────────────────────────────────────────
const CLASS_COLORS = {
  crusader: '#4a8fd0', confessor: '#f0c040', inquisitor: '#a0a0a0',
  ranger: '#44aa44', hexblade: '#cc44cc', mage: '#5588cc',
  bard: '#e08040', blood_knight: '#cc3333', plague_doctor: '#66cc66',
  revenant: '#8888cc', shaman: '#44cccc',
};

function classColor(c) { return CLASS_COLORS[c] || '#888'; }
function fmtClass(c) { return c ? c.split('_').map(w => w[0].toUpperCase() + w.slice(1)).join(' ') : '—'; }
function fmtWinner(w) {
  if (w === 'team_a') return 'Team A Victory';
  if (w === 'team_b') return 'Team B Victory';
  if (w === 'draw') return 'Draw';
  if (w === 'party_wipe') return 'Party Wipe';
  return w || '—';
}

// Stat bar — proportional width relative to a max value
function StatBar({ value, max, color, label, showValue = true }) {
  const pct = max > 0 ? Math.min(100, (value / max) * 100) : 0;
  return (
    <div className="stat-bar-row">
      {label && <span className="stat-bar-label">{label}</span>}
      <div className="stat-bar-track">
        <div className="stat-bar-fill" style={{ width: `${pct}%`, backgroundColor: color }} />
      </div>
      {showValue && <span className="stat-bar-value">{value}</span>}
    </div>
  );
}

export default function MatchDetail({ match, onBack }) {
  if (!match) {
    return (
      <div className="tab-content">
        <div className="empty-state">
          <div className="empty-icon">📋</div>
          <p>Select a match from the History tab to view details.</p>
        </div>
      </div>
    );
  }

  const { teams, unit_stats, summary, timeline } = match;

  // ── Build unit arrays per team ──
  const teamA = useMemo(() => {
    if (!teams?.team_a) return [];
    return teams.team_a.map(u => ({
      ...u,
      ...(unit_stats?.[u.unit_id] || {}),
    }));
  }, [teams, unit_stats]);

  const teamB = useMemo(() => {
    if (!teams?.team_b) return [];
    return teams.team_b.map(u => ({
      ...u,
      ...(unit_stats?.[u.unit_id] || {}),
    }));
  }, [teams, unit_stats]);

  // ── Max values for stat bars ──
  const allUnits = [...teamA, ...teamB];
  const maxDamage  = Math.max(1, ...allUnits.map(u => u.damage_dealt || 0));
  const maxHealing = Math.max(1, ...allUnits.map(u => u.healing_done || 0));
  const maxKills   = Math.max(1, ...allUnits.map(u => u.kills || 0));

  // ── Kill feed from timeline ──
  const killFeed = useMemo(() => {
    if (!timeline) return [];
    const kills = [];
    for (const turn of timeline) {
      for (const evt of (turn.events || [])) {
        if (evt.type === 'death') {
          kills.push({
            turn: turn.turn,
            victim: evt.unit,
            killer: evt.killer || '?',
          });
        }
      }
    }
    return kills;
  }, [timeline]);

  // ── MVP info ──
  const mvpUnit = summary?.mvp && unit_stats?.[summary.mvp]
    ? { ...unit_stats[summary.mvp] }
    : null;

  return (
    <div className="tab-content match-detail">
      {/* ── Header ── */}
      <div className="detail-header">
        <button className="btn btn-secondary btn-back" onClick={onBack}>← Back</button>
        <div className="detail-meta">
          <h2 className="detail-title">{fmtWinner(match.winner)}</h2>
          <div className="detail-info">
            <span className={`type-badge type-${match.match_type}`}>{match.match_type || '—'}</span>
            <span className="detail-map">{match.map_id ? match.map_id.replace(/_/g, ' ') : '—'}</span>
            <span className="detail-turns">{match.duration_turns} turns</span>
            {match.timestamp && (
              <span className="detail-date">{new Date(match.timestamp).toLocaleString()}</span>
            )}
          </div>
        </div>
      </div>

      {/* ── Team Comparison ── */}
      {summary && (
        <div className="team-comparison">
          <div className="comparison-bar">
            <span className="team-label team-a-label">Team A</span>
            <div className="comparison-track">
              <ComparisonBar
                valA={summary.team_a_total_damage || 0}
                valB={summary.team_b_total_damage || 0}
                label="Damage"
              />
              <ComparisonBar
                valA={summary.team_a_total_healing || 0}
                valB={summary.team_b_total_healing || 0}
                label="Healing"
              />
              <ComparisonBar
                valA={summary.team_a_kills || 0}
                valB={summary.team_b_kills || 0}
                label="Kills"
              />
            </div>
            <span className="team-label team-b-label">Team B</span>
          </div>
        </div>
      )}

      {/* ── MVP Card ── */}
      {mvpUnit && (
        <div className="mvp-card">
          <div className="mvp-badge">★ MVP</div>
          <div className="mvp-info">
            <span className="mvp-name">{mvpUnit.username || mvpUnit.unit_id}</span>
            <span className="mvp-class" style={{ color: classColor(mvpUnit.class_id) }}>
              {fmtClass(mvpUnit.class_id)}
            </span>
          </div>
          <div className="mvp-stats">
            <span className="mvp-stat"><em>{mvpUnit.damage_dealt || 0}</em> dmg</span>
            <span className="mvp-stat"><em>{mvpUnit.kills || 0}</em> kills</span>
            <span className="mvp-stat"><em>{mvpUnit.healing_done || 0}</em> heal</span>
          </div>
        </div>
      )}

      {/* ── Scoreboards ── */}
      <div className="scoreboards">
        <TeamScoreboard
          label="Team A"
          units={teamA}
          teamClass="team-a"
          maxDamage={maxDamage}
          maxHealing={maxHealing}
          maxKills={maxKills}
        />
        <TeamScoreboard
          label="Team B"
          units={teamB}
          teamClass="team-b"
          maxDamage={maxDamage}
          maxHealing={maxHealing}
          maxKills={maxKills}
        />
      </div>

      {/* ── Kill Feed ── */}
      {killFeed.length > 0 && (
        <div className="kill-feed-section">
          <h3>Kill Feed</h3>
          <div className="kill-feed">
            {killFeed.map((k, i) => (
              <div key={i} className="kill-entry">
                <span className="kill-turn">Turn {k.turn}</span>
                <span className="kill-killer">{k.killer}</span>
                <span className="kill-arrow">→</span>
                <span className="kill-victim">{k.victim}</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

// ── Team Scoreboard Sub-component ──
function TeamScoreboard({ label, units, teamClass, maxDamage, maxHealing, maxKills }) {
  if (!units || units.length === 0) {
    return (
      <div className={`scoreboard ${teamClass}`}>
        <h3 className="scoreboard-title">{label}</h3>
        <p className="hint">No unit data</p>
      </div>
    );
  }

  return (
    <div className={`scoreboard ${teamClass}`}>
      <h3 className="scoreboard-title">{label}</h3>
      <table className="scoreboard-table">
        <thead>
          <tr>
            <th>Unit</th>
            <th>Class</th>
            <th>Status</th>
            <th>Damage</th>
            <th>Healing</th>
            <th>Kills</th>
            <th>Deaths</th>
          </tr>
        </thead>
        <tbody>
          {units.map(u => (
            <tr key={u.unit_id} className={u.status === 'died' || u.deaths > 0 ? 'unit-dead' : ''}>
              <td className="td-unit">
                <span className="unit-name">{u.username || u.unit_id}</span>
                {u.is_ai && <span className="ai-badge">AI</span>}
              </td>
              <td>
                <span className="class-tag" style={{ color: classColor(u.class_id) }}>
                  {fmtClass(u.class_id)}
                </span>
              </td>
              <td>
                <span className={`status-tag status-${u.status || (u.deaths > 0 ? 'died' : 'survived')}`}>
                  {u.status || (u.deaths > 0 ? 'died' : 'survived')}
                </span>
              </td>
              <td>
                <StatBar value={u.damage_dealt || 0} max={maxDamage} color="var(--red)" />
              </td>
              <td>
                <StatBar value={u.healing_done || 0} max={maxHealing} color="var(--green)" />
              </td>
              <td className="td-num">{u.kills || 0}</td>
              <td className="td-num">{u.deaths || 0}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

// ── Team Comparison Bar ──
function ComparisonBar({ valA, valB, label }) {
  const total = valA + valB;
  const pctA = total > 0 ? (valA / total) * 100 : 50;

  return (
    <div className="comparison-row">
      <span className="comparison-val comp-val-a">{valA.toLocaleString()}</span>
      <div className="comparison-meter">
        <div className="comparison-fill-a" style={{ width: `${pctA}%` }} />
        <div className="comparison-fill-b" style={{ width: `${100 - pctA}%` }} />
        <span className="comparison-label">{label}</span>
      </div>
      <span className="comparison-val comp-val-b">{valB.toLocaleString()}</span>
    </div>
  );
}
