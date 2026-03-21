import React, { useMemo } from 'react';

const TEAM_LABELS = { a: 'Team A', b: 'Team B', c: 'Team C', d: 'Team D' };
const TEAM_KEYS = ['a', 'b', 'c', 'd'];

export default function EquipmentReport({ match, onBack }) {
  if (!match) {
    return (
      <div className="no-match-msg">
        <p>No match selected</p>
        <button className="btn" onClick={onBack}>← Back to Browser</button>
      </div>
    );
  }

  const unitStats = match.unit_stats || {};
  const timeline = match.timeline || [];
  const teams = match.teams || {};

  // Build equipment data from team rosters
  const rosterData = useMemo(() => {
    const data = {};
    for (const [teamKey, roster] of Object.entries(teams)) {
      const tk = teamKey.replace('team_', '');
      if (!TEAM_KEYS.includes(tk)) continue;
      if (!Array.isArray(roster)) continue;

      data[tk] = roster
        .filter(u => u.team === tk) // Only hero units, not PVE mixed in
        .map(u => ({
          unit_id: u.unit_id || u.player_id,
          username: u.username || '?',
          class_id: u.class_id || '?',
          team: tk,
          weapon: u.weapon || u.equipment?.weapon || null,
          armor: u.armor || u.equipment?.armor || null,
          accessory: u.accessory || u.equipment?.accessory || null,
          hp: u.hp,
          max_hp: u.max_hp,
          attack: u.attack,
          defense: u.defense,
        }));
    }
    return data;
  }, [teams]);

  // Analyze item events from timeline
  const itemEvents = useMemo(() => {
    const events = { pickups: 0, equips: 0, trades: 0, potionsUsed: 0 };
    const perTeam = {};
    for (const tk of TEAM_KEYS) {
      perTeam[tk] = { pickups: 0, equips: 0, itemsLooted: 0 };
    }

    for (const [uid, u] of Object.entries(unitStats)) {
      const tk = u.team;
      if (tk && perTeam[tk]) {
        perTeam[tk].itemsLooted += u.items_looted || 0;
        events.pickups += u.items_looted || 0;
      }
    }

    // Count item-related events in timeline
    for (const turnData of timeline) {
      for (const ev of (turnData.events || [])) {
        if (ev.type === 'item_pickup') events.pickups++;
        if (ev.type === 'equip') events.equips++;
        if (ev.type === 'trade') events.trades++;
        if (ev.type === 'potion' || ev.type === 'item_use') events.potionsUsed++;
      }
    }

    return { events, perTeam };
  }, [timeline, unitStats]);

  return (
    <div className="tab-content">
      <div className="tab-header">
        <h2>Equipment Report</h2>
        <div className="header-actions">
          <span style={{ fontFamily: 'monospace', fontSize: 12, color: 'var(--text-dim)' }}>
            {match.match_id?.substring(0, 8)}
          </span>
          <button className="btn btn-small" onClick={onBack}>← Browser</button>
        </div>
      </div>

      {/* Item Economy Overview */}
      <div className="card-grid">
        <div className="card">
          <div className="card-header">
            <span className="card-label">Items Looted</span>
          </div>
          <div className="card-value">{itemEvents.events.pickups}</div>
          <div className="card-sub">Across all teams</div>
        </div>
        <div className="card">
          <div className="card-header">
            <span className="card-label">Items Equipped</span>
          </div>
          <div className="card-value">{itemEvents.events.equips}</div>
          <div className="card-sub">Auto-equipped upgrades</div>
        </div>
        <div className="card">
          <div className="card-header">
            <span className="card-label">Potions Used</span>
          </div>
          <div className="card-value">{itemEvents.events.potionsUsed}</div>
          <div className="card-sub">Consumed in combat</div>
        </div>
      </div>

      {/* Items Looted Per Team */}
      <div className="panel">
        <div className="panel-title">Items Looted Per Team</div>
        {TEAM_KEYS.map(tk => {
          const looted = itemEvents.perTeam[tk]?.itemsLooted || 0;
          const maxLooted = Math.max(...TEAM_KEYS.map(t => itemEvents.perTeam[t]?.itemsLooted || 0), 1);
          const pct = (looted / maxLooted) * 100;
          return (
            <div key={tk} className="stat-row">
              <span className={`stat-label team-${tk}`}>{TEAM_LABELS[tk]}</span>
              <div className="stat-bar-bg">
                <div className={`stat-bar-fill bar-${tk}`} style={{ width: `${pct}%` }} />
                <span className="stat-bar-text">{looted} items</span>
              </div>
            </div>
          );
        })}
      </div>

      {/* Per-Team Roster Equipment */}
      {TEAM_KEYS.map(tk => {
        const roster = rosterData[tk];
        if (!roster || roster.length === 0) return null;

        return (
          <div key={tk} className="panel">
            <div className={`panel-title team-${tk}`}>{TEAM_LABELS[tk]} Equipment</div>
            <table className="scoreboard">
              <thead>
                <tr>
                  <th>Hero</th>
                  <th>Class</th>
                  <th>Weapon</th>
                  <th>Armor</th>
                  <th>Accessory</th>
                  <th className="td-num">HP</th>
                  <th className="td-num">ATK</th>
                  <th className="td-num">DEF</th>
                </tr>
              </thead>
              <tbody>
                {roster.map((u, i) => {
                  const stat = Object.values(unitStats).find(s => s.username === u.username && s.team === tk);
                  const isDead = stat?.status === 'died';
                  return (
                    <tr key={i} className={isDead ? 'unit-dead' : ''}>
                      <td className="unit-name">{u.username}</td>
                      <td className="unit-class">{u.class_id}</td>
                      <td>{formatItem(u.weapon)}</td>
                      <td>{formatItem(u.armor)}</td>
                      <td>{formatItem(u.accessory)}</td>
                      <td className="td-num">{u.max_hp || u.hp || '—'}</td>
                      <td className="td-num">{u.attack || '—'}</td>
                      <td className="td-num">{u.defense || '—'}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        );
      })}

      {/* Per-Hero Performance vs Items */}
      <div className="panel">
        <div className="panel-title">Hero Performance & Loot</div>
        <table className="scoreboard">
          <thead>
            <tr>
              <th>Team</th>
              <th>Hero</th>
              <th>Class</th>
              <th className="td-num">Damage</th>
              <th className="td-num">Healing</th>
              <th className="td-num">Kills</th>
              <th className="td-num">Items Looted</th>
              <th className="td-num">Turns Survived</th>
              <th>Status</th>
            </tr>
          </thead>
          <tbody>
            {TEAM_KEYS.flatMap(tk =>
              Object.entries(unitStats)
                .filter(([_, u]) => u.team === tk)
                .sort((a, b) => (b[1].items_looted || 0) - (a[1].items_looted || 0))
                .map(([uid, u]) => (
                  <tr key={uid} className={u.status === 'died' ? 'unit-dead' : ''}>
                    <td><span className={`team-badge badge-${tk}`}>{tk.toUpperCase()}</span></td>
                    <td className="unit-name">{u.username || uid.substring(0, 8)}</td>
                    <td className="unit-class">{u.class_id}</td>
                    <td className="td-num">{(u.damage_dealt || 0).toLocaleString()}</td>
                    <td className="td-num">{(u.healing_done || 0).toLocaleString()}</td>
                    <td className="td-num">{u.kills || 0}</td>
                    <td className="td-num" style={{ color: (u.items_looted || 0) > 0 ? 'var(--gold)' : 'var(--text-dim)' }}>
                      {u.items_looted || 0}
                    </td>
                    <td className="td-num">{u.turns_survived || '—'}</td>
                    <td>{u.status === 'survived'
                      ? <span style={{ color: 'var(--green)' }}>Alive</span>
                      : <span style={{ color: 'var(--red)' }}>Dead</span>}
                    </td>
                  </tr>
                ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function formatItem(item) {
  if (!item) return <span style={{ color: 'var(--text-dim)' }}>(empty)</span>;
  if (typeof item === 'string') return item;
  const name = item.name || '?';
  const rarity = item.rarity || '';
  const rarityColors = {
    common: 'var(--text-dim)',
    uncommon: 'var(--green)',
    rare: 'var(--blue)',
    epic: 'var(--purple)',
    legendary: 'var(--gold)',
    unique: 'var(--accent-light)',
  };
  const color = rarityColors[rarity?.toLowerCase()] || 'var(--text)';
  return <span style={{ color }}>{name}{rarity ? ` [${rarity}]` : ''}</span>;
}
