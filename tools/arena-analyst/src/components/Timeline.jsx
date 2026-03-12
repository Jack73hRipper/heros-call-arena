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

// ── Event type icons/colors ──
const EVENT_STYLES = {
  damage:     { icon: '⚔', color: 'var(--red)' },
  heal:       { icon: '✚', color: 'var(--green)' },
  death:      { icon: '💀', color: '#ff4444' },
  move:       { icon: '→', color: 'var(--text-dim)' },
  buff:       { icon: '▲', color: 'var(--blue)' },
  elite_kill: { icon: '👑', color: 'var(--gold)' },
};

function eventStyle(type) { return EVENT_STYLES[type] || { icon: '·', color: 'var(--text-dim)' }; }

export default function Timeline({ matches, onFetchDetail }) {
  const [selectedMatchId, setSelectedMatchId] = useState(null);
  const [match, setMatch] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [filterTypes, setFilterTypes] = useState(new Set(['damage', 'heal', 'death', 'buff', 'elite_kill']));
  const [selectedTurn, setSelectedTurn] = useState(null);

  // Load match detail when selection changes
  useEffect(() => {
    if (!selectedMatchId) return;
    loadMatch(selectedMatchId);
  }, [selectedMatchId]);

  async function loadMatch(matchId) {
    setLoading(true);
    setError(null);
    setSelectedTurn(null);
    try {
      const res = await fetch(`/api/matches/${matchId}`);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      setMatch(data);
    } catch (err) {
      setError(err.message);
      setMatch(null);
    } finally {
      setLoading(false);
    }
  }

  function toggleFilter(type) {
    setFilterTypes(prev => {
      const next = new Set(prev);
      if (next.has(type)) next.delete(type);
      else next.add(type);
      return next;
    });
  }

  // ── Compute damage curves (cumulative damage per team over time) ──
  const damageCurves = useMemo(() => {
    if (!match?.timeline || !match.unit_stats) return null;

    // Build unit→team lookup
    const unitTeam = {};
    if (match.teams) {
      for (const u of (match.teams.team_a || [])) unitTeam[u.unit_id] = 'a';
      for (const u of (match.teams.team_b || [])) unitTeam[u.unit_id] = 'b';
    }

    const teamACum = [];
    const teamBCum = [];
    let totalA = 0, totalB = 0;

    for (const turn of match.timeline) {
      for (const evt of (turn.events || [])) {
        if (evt.type === 'damage') {
          const team = unitTeam[evt.src];
          if (team === 'a') totalA += evt.dmg || 0;
          else if (team === 'b') totalB += evt.dmg || 0;
        }
      }
      teamACum.push(totalA);
      teamBCum.push(totalB);
    }

    const maxDmg = Math.max(1, totalA, totalB);
    return { teamA: teamACum, teamB: teamBCum, maxDmg };
  }, [match]);

  // ── HP timeline (estimated from damage_taken events) ──
  const hpTimeline = useMemo(() => {
    if (!match?.timeline || !match.unit_stats || !match.teams) return null;

    // Build initial HP map from team rosters
    const hpMap = {}; // unit_id → { current, max, team }
    for (const u of (match.teams.team_a || [])) {
      hpMap[u.unit_id] = { max: u.base_hp || 100, current: u.base_hp || 100, team: 'a', class_id: u.class_id };
    }
    for (const u of (match.teams.team_b || [])) {
      hpMap[u.unit_id] = { max: u.base_hp || 100, current: u.base_hp || 100, team: 'b', class_id: u.class_id };
    }

    // Rebuild HP per turn
    const perTurn = []; // [ { unit_id: hp, ... } per turn ]
    for (const turn of match.timeline) {
      for (const evt of (turn.events || [])) {
        if (evt.type === 'damage' && hpMap[evt.tgt]) {
          hpMap[evt.tgt].current = Math.max(0, hpMap[evt.tgt].current - (evt.dmg || 0));
        }
        if (evt.type === 'heal' && hpMap[evt.tgt]) {
          hpMap[evt.tgt].current = Math.min(hpMap[evt.tgt].max, hpMap[evt.tgt].current + (evt.amt || 0));
        }
        if (evt.type === 'death' && hpMap[evt.unit]) {
          hpMap[evt.unit].current = 0;
        }
      }
      const snapshot = {};
      for (const [uid, data] of Object.entries(hpMap)) {
        snapshot[uid] = { ...data };
      }
      perTurn.push(snapshot);
    }

    return perTurn;
  }, [match]);

  // ── Death markers ──
  const deathMarkers = useMemo(() => {
    if (!match?.timeline) return [];
    const markers = [];
    for (const turn of match.timeline) {
      for (const evt of (turn.events || [])) {
        if (evt.type === 'death') {
          markers.push({ turn: turn.turn, unit: evt.unit, killer: evt.killer });
        }
      }
    }
    return markers;
  }, [match]);

  // ── Filtered events for selected turn ──
  const turnEvents = useMemo(() => {
    if (!match?.timeline || selectedTurn === null) return [];
    const turn = match.timeline.find(t => t.turn === selectedTurn);
    if (!turn) return [];
    return (turn.events || []).filter(e => filterTypes.has(e.type));
  }, [match, selectedTurn, filterTypes]);

  const totalTurns = match?.timeline?.length || 0;

  return (
    <div className="tab-content timeline-view">
      <div className="tab-header">
        <h2>Timeline Replay</h2>
      </div>

      {/* ── Match Selector ── */}
      <div className="timeline-selector">
        <label className="filter-label">Select Match</label>
        <select
          className="filter-select timeline-match-select"
          value={selectedMatchId || ''}
          onChange={e => setSelectedMatchId(e.target.value || null)}
        >
          <option value="">— Choose a match —</option>
          {(matches || []).map(m => (
            <option key={m.match_id} value={m.match_id}>
              {m.timestamp ? new Date(m.timestamp).toLocaleDateString() : '?'} — {m.map_id?.replace(/_/g, ' ') || '?'} ({m.match_type}) — {m.duration_turns}t
            </option>
          ))}
        </select>
      </div>

      {loading && <div className="loading">Loading match timeline...</div>}
      {error && <div className="error-msg">Error: {error}</div>}

      {!loading && !match && !error && (
        <div className="empty-state">
          <div className="empty-icon">⏱️</div>
          <p>Select a match above to view the turn-by-turn timeline.</p>
        </div>
      )}

      {match && match.timeline && (
        <>
          {/* ── Match Summary Banner ── */}
          <div className="timeline-banner">
            <span className={`type-badge type-${match.match_type}`}>{match.match_type}</span>
            <span className="detail-map">{match.map_id?.replace(/_/g, ' ')}</span>
            <span className="detail-turns">{match.duration_turns} turns</span>
            <span className="timeline-winner">
              Winner: <strong>{match.winner === 'team_a' ? 'Team A' : match.winner === 'team_b' ? 'Team B' : match.winner}</strong>
            </span>
          </div>

          {/* ── Damage Curve Chart ── */}
          {damageCurves && totalTurns > 0 && (
            <div className="timeline-section">
              <div className="section-title">Cumulative Damage Over Time</div>
              <div className="damage-curve-chart">
                <div className="curve-labels">
                  <span className="curve-label curve-label-a">Team A: {damageCurves.teamA[totalTurns - 1]?.toLocaleString()}</span>
                  <span className="curve-label curve-label-b">Team B: {damageCurves.teamB[totalTurns - 1]?.toLocaleString()}</span>
                </div>
                <div className="curve-canvas">
                  {/* SVG chart */}
                  <svg viewBox={`0 0 ${totalTurns} 100`} preserveAspectRatio="none" className="curve-svg">
                    {/* Team A line */}
                    <polyline
                      points={damageCurves.teamA.map((v, i) =>
                        `${i},${100 - (v / damageCurves.maxDmg) * 95}`
                      ).join(' ')}
                      fill="none"
                      stroke="var(--team-a)"
                      strokeWidth="1.5"
                      vectorEffect="non-scaling-stroke"
                    />
                    {/* Team B line */}
                    <polyline
                      points={damageCurves.teamB.map((v, i) =>
                        `${i},${100 - (v / damageCurves.maxDmg) * 95}`
                      ).join(' ')}
                      fill="none"
                      stroke="var(--team-b)"
                      strokeWidth="1.5"
                      vectorEffect="non-scaling-stroke"
                    />
                    {/* Death markers */}
                    {deathMarkers.map((d, idx) => (
                      <line
                        key={idx}
                        x1={d.turn - 1}
                        y1="0"
                        x2={d.turn - 1}
                        y2="100"
                        stroke="rgba(255,68,68,0.4)"
                        strokeWidth="0.5"
                        vectorEffect="non-scaling-stroke"
                        strokeDasharray="3,2"
                      />
                    ))}
                    {/* Selected turn marker */}
                    {selectedTurn !== null && (
                      <line
                        x1={selectedTurn - 1}
                        y1="0"
                        x2={selectedTurn - 1}
                        y2="100"
                        stroke="var(--accent-light)"
                        strokeWidth="1"
                        vectorEffect="non-scaling-stroke"
                      />
                    )}
                  </svg>
                  {/* Turn axis */}
                  <div className="curve-axis">
                    <span>Turn 1</span>
                    <span>Turn {Math.ceil(totalTurns / 2)}</span>
                    <span>Turn {totalTurns}</span>
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* ── Turn-by-Turn Scrubber ── */}
          <div className="timeline-section">
            <div className="section-title">Turn-by-Turn Events</div>

            {/* Event type filters */}
            <div className="timeline-filters">
              {Object.entries(EVENT_STYLES).map(([type, style]) => (
                <button
                  key={type}
                  className={`timeline-filter-btn ${filterTypes.has(type) ? 'active' : ''}`}
                  style={{ '--filter-color': style.color }}
                  onClick={() => toggleFilter(type)}
                >
                  <span className="filter-icon">{style.icon}</span> {type}
                </button>
              ))}
            </div>

            {/* Turn bar (clickable timeline strip) */}
            <div className="turn-strip">
              {match.timeline.map((turn) => {
                const hasDeaths = (turn.events || []).some(e => e.type === 'death');
                const eventCount = (turn.events || []).filter(e => filterTypes.has(e.type)).length;
                const isSelected = selectedTurn === turn.turn;
                return (
                  <div
                    key={turn.turn}
                    className={`turn-cell ${isSelected ? 'turn-selected' : ''} ${hasDeaths ? 'turn-has-death' : ''}`}
                    onClick={() => setSelectedTurn(turn.turn)}
                    title={`Turn ${turn.turn} — ${eventCount} events`}
                  >
                    <div
                      className="turn-cell-bar"
                      style={{ height: `${Math.min(100, eventCount * 12)}%` }}
                    />
                  </div>
                );
              })}
            </div>
            <div className="turn-strip-labels">
              <span>Turn 1</span>
              <span>Turn {totalTurns}</span>
            </div>

            {/* Selected turn detail */}
            {selectedTurn !== null && (
              <div className="turn-detail">
                <h4 className="turn-detail-title">Turn {selectedTurn}</h4>
                {turnEvents.length === 0 ? (
                  <p className="hint">No events matching filters for this turn.</p>
                ) : (
                  <div className="turn-events">
                    {turnEvents.map((evt, idx) => (
                      <TurnEvent key={idx} event={evt} unitStats={match.unit_stats} />
                    ))}
                  </div>
                )}
              </div>
            )}

            {selectedTurn === null && (
              <div className="turn-detail turn-detail-empty">
                <p className="hint">Click a turn bar above to view events for that turn.</p>
              </div>
            )}
          </div>

          {/* ── Death Timeline ── */}
          {deathMarkers.length > 0 && (
            <div className="timeline-section">
              <div className="section-title">Death Timeline</div>
              <div className="death-timeline">
                {deathMarkers.map((d, i) => {
                  const unitData = match.unit_stats?.[d.unit];
                  const killerData = match.unit_stats?.[d.killer];
                  return (
                    <div key={i} className="death-marker-row">
                      <span className="death-turn-badge">T{d.turn}</span>
                      <span className="death-killer" style={{ color: killerData ? classColor(killerData.class_id) : 'var(--text)' }}>
                        {killerData?.username || d.killer || '?'}
                      </span>
                      <span className="kill-arrow">→</span>
                      <span className="death-victim" style={{ color: unitData ? classColor(unitData.class_id) : 'var(--red)' }}>
                        {unitData?.username || d.unit}
                      </span>
                      <span className="death-class-info">
                        {unitData && <span className="class-tag" style={{ color: classColor(unitData.class_id) }}>({fmtClass(unitData.class_id)})</span>}
                      </span>
                    </div>
                  );
                })}
              </div>
            </div>
          )}
        </>
      )}

      {match && !match.timeline && (
        <div className="empty-state">
          <div className="empty-icon">⚠️</div>
          <p>This match has no timeline data.</p>
          <p className="hint">Timeline data is only recorded for matches played after the Arena Analyst was installed.</p>
        </div>
      )}
    </div>
  );
}

// ── Single Turn Event Row ──
function TurnEvent({ event, unitStats }) {
  const style = eventStyle(event.type);

  function unitName(uid) {
    const u = unitStats?.[uid];
    return u?.username || uid || '?';
  }

  function unitColor(uid) {
    const u = unitStats?.[uid];
    return u ? classColor(u.class_id) : 'var(--text)';
  }

  let description;
  switch (event.type) {
    case 'damage':
      description = (
        <>
          <span style={{ color: unitColor(event.src) }}>{unitName(event.src)}</span>
          {' dealt '}
          <em className="evt-value evt-damage">{event.dmg}</em>
          {' to '}
          <span style={{ color: unitColor(event.tgt) }}>{unitName(event.tgt)}</span>
          <span className="evt-skill">({event.skill})</span>
          {event.crit && <span className="evt-crit">CRIT</span>}
        </>
      );
      break;
    case 'heal':
      description = (
        <>
          <span style={{ color: unitColor(event.src) }}>{unitName(event.src)}</span>
          {' healed '}
          <span style={{ color: unitColor(event.tgt) }}>{unitName(event.tgt)}</span>
          {' for '}
          <em className="evt-value evt-heal">{event.amt}</em>
          <span className="evt-skill">({event.skill})</span>
        </>
      );
      break;
    case 'death':
      description = (
        <>
          <span style={{ color: unitColor(event.unit) }}>{unitName(event.unit)}</span>
          {' was killed'}
          {event.killer && (
            <>
              {' by '}
              <span style={{ color: unitColor(event.killer) }}>{unitName(event.killer)}</span>
            </>
          )}
        </>
      );
      break;
    case 'buff':
      description = (
        <>
          <span style={{ color: unitColor(event.src) }}>{unitName(event.src)}</span>
          {' applied '}
          <em className="evt-value evt-buff">{event.buff}</em>
          {event.tgt && (
            <>
              {' on '}
              <span style={{ color: unitColor(event.tgt) }}>{unitName(event.tgt)}</span>
            </>
          )}
        </>
      );
      break;
    case 'move':
      description = (
        <>
          <span style={{ color: unitColor(event.unit) }}>{unitName(event.unit)}</span>
          {' moved to '}
          <em className="evt-value">[{event.to?.join(', ')}]</em>
        </>
      );
      break;
    case 'elite_kill':
      description = (
        <>
          <span style={{ color: unitColor(event.killer) }}>{unitName(event.killer)}</span>
          {' slew elite '}
          <span className="evt-value evt-elite">{unitName(event.unit)}</span>
        </>
      );
      break;
    default:
      description = <span>{JSON.stringify(event)}</span>;
  }

  return (
    <div className="turn-event">
      <span className="turn-event-icon" style={{ color: style.color }}>{style.icon}</span>
      <span className="turn-event-type" style={{ color: style.color }}>{event.type}</span>
      <span className="turn-event-desc">{description}</span>
    </div>
  );
}
