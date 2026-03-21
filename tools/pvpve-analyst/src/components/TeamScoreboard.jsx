import React, { useMemo } from 'react';

const TEAM_LABELS = { a: 'Team A', b: 'Team B', c: 'Team C', d: 'Team D' };
const TEAM_KEYS = ['a', 'b', 'c', 'd'];

function winnerLabel(w) {
  if (!w) return '—';
  const k = w.replace('team_', '');
  return TEAM_LABELS[k] || w;
}

function StatBar({ label, values, maxVal, teams }) {
  if (!maxVal) maxVal = Math.max(...values, 1);
  return (
    <div style={{ marginBottom: 10 }}>
      <div style={{ fontSize: 11, color: 'var(--text-dim)', marginBottom: 4, textTransform: 'uppercase', letterSpacing: 0.5 }}>{label}</div>
      {teams.map((tk, i) => (
        <div key={tk} className="stat-row">
          <span className={`stat-label team-${tk}`}>{TEAM_LABELS[tk]}</span>
          <div className="stat-bar-bg">
            <div className={`stat-bar-fill bar-${tk}`} style={{ width: `${(values[i] / maxVal) * 100}%` }} />
            <span className="stat-bar-text">{values[i].toLocaleString()}</span>
          </div>
        </div>
      ))}
    </div>
  );
}

export default function TeamScoreboard({ match, onBack }) {
  if (!match) {
    return (
      <div className="no-match-msg">
        <p>No match selected</p>
        <button className="btn" onClick={onBack}>← Back to Browser</button>
      </div>
    );
  }

  const unitStats = match.unit_stats || {};
  const summary = match.summary || {};

  // Group units by team
  const teamUnits = useMemo(() => {
    const teams = { a: [], b: [], c: [], d: [], pve: [] };
    for (const [uid, u] of Object.entries(unitStats)) {
      const tk = u.team || 'pve';
      if (teams[tk]) teams[tk].push({ ...u, unit_id: uid });
    }
    // Sort each team: alive first, then by damage descending
    for (const tk of Object.keys(teams)) {
      teams[tk].sort((a, b) => {
        if (a.status !== b.status) return a.status === 'survived' ? -1 : 1;
        return (b.damage_dealt || 0) - (a.damage_dealt || 0);
      });
    }
    return teams;
  }, [unitStats]);

  // Aggregate stats per team
  const teamTotals = useMemo(() => {
    const totals = {};
    for (const tk of [...TEAM_KEYS, 'pve']) {
      const units = teamUnits[tk] || [];
      totals[tk] = {
        count: units.length,
        alive: units.filter(u => u.status === 'survived').length,
        damage: units.reduce((s, u) => s + (u.damage_dealt || 0), 0),
        healing: units.reduce((s, u) => s + (u.healing_done || 0), 0),
        kills: units.reduce((s, u) => s + (u.kills || 0), 0),
        deaths: units.reduce((s, u) => s + (u.deaths || 0), 0),
        bossKills: units.reduce((s, u) => s + (u.boss_kills || 0), 0),
        items: units.reduce((s, u) => s + (u.items_looted || 0), 0),
      };
    }
    return totals;
  }, [teamUnits]);

  const maxDmg = Math.max(...TEAM_KEYS.map(tk => teamTotals[tk].damage), 1);
  const maxHeal = Math.max(...TEAM_KEYS.map(tk => teamTotals[tk].healing), 1);
  const maxKills = Math.max(...TEAM_KEYS.map(tk => teamTotals[tk].kills), 1);

  return (
    <div className="tab-content">
      <div className="tab-header">
        <h2>4-Team Scoreboard</h2>
        <div className="header-actions">
          <span style={{ fontFamily: 'monospace', fontSize: 12, color: 'var(--text-dim)' }}>
            {match.match_id?.substring(0, 8)}
          </span>
          <button className="btn btn-small" onClick={onBack}>← Browser</button>
        </div>
      </div>

      {/* Match Info */}
      <div className="panel" style={{ display: 'flex', gap: 24, flexWrap: 'wrap', alignItems: 'center' }}>
        <div>
          <span style={{ fontSize: 11, color: 'var(--text-dim)' }}>WINNER</span>
          <div style={{ fontSize: 22, fontWeight: 700 }} className={`winner-${(match.winner || '').replace('team_', '')}`}>
            {winnerLabel(match.winner)}
          </div>
        </div>
        <div>
          <span style={{ fontSize: 11, color: 'var(--text-dim)' }}>TURNS</span>
          <div style={{ fontSize: 22, fontWeight: 700, color: 'var(--text-bright)' }}>{match.duration_turns}</div>
        </div>
        <div>
          <span style={{ fontSize: 11, color: 'var(--text-dim)' }}>MVP</span>
          <div style={{ fontSize: 16, fontWeight: 600, color: 'var(--gold)' }}>{summary.mvp || '—'}</div>
          <div style={{ fontSize: 11, color: 'var(--text-dim)' }}>{summary.mvp_damage ? `${summary.mvp_damage} dmg` : ''} {summary.mvp_kills ? `${summary.mvp_kills} kills` : ''}</div>
        </div>
        <div>
          <span style={{ fontSize: 11, color: 'var(--text-dim)' }}>FIRST BLOOD</span>
          <div style={{ fontSize: 13, color: 'var(--red)' }}>
            {summary.first_blood_killer ? `${summary.first_blood_killer} → ${summary.first_blood_victim} (T${summary.first_blood_turn})` : '—'}
          </div>
        </div>
        <div>
          <span style={{ fontSize: 11, color: 'var(--text-dim)' }}>PVE ENEMIES</span>
          <div style={{ fontSize: 16, fontWeight: 600, color: 'var(--team-pve)' }}>{teamTotals.pve?.count || 0}</div>
        </div>
      </div>

      {/* Comparative Bars */}
      <div className="two-col">
        <div className="panel">
          <div className="panel-title">Total Damage</div>
          <StatBar label="" values={TEAM_KEYS.map(tk => teamTotals[tk].damage)} maxVal={maxDmg} teams={TEAM_KEYS} />
        </div>
        <div className="panel">
          <div className="panel-title">Total Healing</div>
          <StatBar label="" values={TEAM_KEYS.map(tk => teamTotals[tk].healing)} maxVal={maxHeal} teams={TEAM_KEYS} />
        </div>
      </div>

      {/* Team Summary Cards */}
      <div className="card-grid" style={{ gridTemplateColumns: 'repeat(4, 1fr)' }}>
        {TEAM_KEYS.map(tk => {
          const t = teamTotals[tk];
          const isWinner = match.winner === tk || match.winner === `team_${tk}`;
          return (
            <div key={tk} className="card" style={{ borderColor: isWinner ? `var(--team-${tk})` : undefined }}>
              <div className="card-header">
                <span className={`card-label team-${tk}`}>{TEAM_LABELS[tk]}</span>
                {isWinner && <span style={{ fontSize: 14 }}>👑</span>}
              </div>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '6px 16px', fontSize: 13 }}>
                <div><span style={{ color: 'var(--text-dim)' }}>Alive:</span> {t.alive}/{t.count}</div>
                <div><span style={{ color: 'var(--text-dim)' }}>Kills:</span> <span style={{ color: 'var(--green)' }}>{t.kills}</span></div>
                <div><span style={{ color: 'var(--text-dim)' }}>Deaths:</span> <span style={{ color: 'var(--red)' }}>{t.deaths}</span></div>
                <div><span style={{ color: 'var(--text-dim)' }}>Damage:</span> {t.damage.toLocaleString()}</div>
                <div><span style={{ color: 'var(--text-dim)' }}>Healing:</span> {t.healing.toLocaleString()}</div>
                <div><span style={{ color: 'var(--text-dim)' }}>Items:</span> {t.items}</div>
                {t.bossKills > 0 && <div><span style={{ color: 'var(--gold)' }}>Boss Kills: {t.bossKills}</span></div>}
              </div>
            </div>
          );
        })}
      </div>

      {/* Per-Team Unit Tables */}
      {TEAM_KEYS.map(tk => {
        const units = teamUnits[tk] || [];
        if (units.length === 0) return null;
        return (
          <div key={tk} className="panel">
            <div className={`panel-title team-${tk}`}>{TEAM_LABELS[tk]} Roster ({teamTotals[tk].alive}/{units.length} alive)</div>
            <table className="scoreboard">
              <thead>
                <tr>
                  <th>Hero</th>
                  <th>Class</th>
                  <th>Status</th>
                  <th>Damage</th>
                  <th>Healing</th>
                  <th>Kills</th>
                  <th>Deaths</th>
                  <th>Turns</th>
                  <th>Items</th>
                  <th>Highest Hit</th>
                </tr>
              </thead>
              <tbody>
                {units.map(u => (
                  <tr key={u.unit_id} className={u.status === 'died' ? 'unit-dead' : ''}>
                    <td className="unit-name">{u.username || u.unit_id?.substring(0, 8)}</td>
                    <td className="unit-class">{u.class_id || '—'}</td>
                    <td>{u.status === 'survived'
                      ? <span style={{ color: 'var(--green)' }}>Alive</span>
                      : <span style={{ color: 'var(--red)' }}>Dead</span>}
                    </td>
                    <td className="td-num">{(u.damage_dealt || 0).toLocaleString()}</td>
                    <td className="td-num">{(u.healing_done || 0).toLocaleString()}</td>
                    <td className="td-num">{u.kills || 0}</td>
                    <td className="td-num">{u.deaths || 0}</td>
                    <td className="td-num">{u.turns_survived || '—'}</td>
                    <td className="td-num">{u.items_looted || 0}</td>
                    <td className="td-num">{u.highest_hit || '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        );
      })}

      {/* PVE Enemy Summary */}
      {teamUnits.pve.length > 0 && (
        <div className="panel">
          <div className="panel-title team-pve">PVE Enemies ({teamTotals.pve.count} total, {teamTotals.pve.count - teamTotals.pve.alive} killed)</div>
          <PveSummary units={teamUnits.pve} />
        </div>
      )}
    </div>
  );
}

function PveSummary({ units }) {
  // Group PVE enemies by class_id for a compact overview
  const groups = useMemo(() => {
    const map = {};
    for (const u of units) {
      const cls = u.class_id || 'unknown';
      if (!map[cls]) map[cls] = { class_id: cls, count: 0, killed: 0, totalDmg: 0, totalHP: 0 };
      map[cls].count++;
      if (u.status === 'died') map[cls].killed++;
      map[cls].totalDmg += u.damage_dealt || 0;
    }
    return Object.values(map).sort((a, b) => b.count - a.count);
  }, [units]);

  return (
    <table className="scoreboard">
      <thead>
        <tr>
          <th>Enemy Type</th>
          <th className="td-num">Count</th>
          <th className="td-num">Killed</th>
          <th className="td-num">Survived</th>
          <th className="td-num">Total Damage Dealt</th>
        </tr>
      </thead>
      <tbody>
        {groups.map(g => (
          <tr key={g.class_id}>
            <td style={{ textTransform: 'capitalize' }}>{g.class_id.replace(/_/g, ' ')}</td>
            <td className="td-num">{g.count}</td>
            <td className="td-num" style={{ color: 'var(--red)' }}>{g.killed}</td>
            <td className="td-num" style={{ color: 'var(--green)' }}>{g.count - g.killed}</td>
            <td className="td-num">{g.totalDmg.toLocaleString()}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
