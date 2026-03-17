import React from 'react';

/**
 * DeployedForces — Team composition display for the new MatchLobby.
 *
 * Phase L1: Basic team display with ★ human / 🤖 AI icons.
 * Phase L3: Live N/5 team counters, owner labels on contributed AI heroes,
 *           "Team Full" indicator.
 */

const TEAM_CONFIG = {
  a: { label: 'Team A', color: '#4a8fd0', colorName: 'Blue' },
  b: { label: 'Team B', color: '#e04040', colorName: 'Red' },
  c: { label: 'Team C', color: '#40c040', colorName: 'Green' },
  d: { label: 'Team D', color: '#d4a017', colorName: 'Gold' },
};

export default function DeployedForces({
  lobbyPlayers,
  playerId,
  config,
  isReady,
  onTeamChange,
  availableClasses,
  teamSlots,
}) {
  // Group players by team
  const teams = { a: [], b: [], c: [], d: [] };
  Object.entries(lobbyPlayers).forEach(([pid, player]) => {
    const team = player.team || 'a';
    if (teams[team]) {
      teams[team].push({ pid, ...player });
    }
  });

  // Determine which teams to display based on config
  const teamCount = config.pvpve_team_count ?? 2;
  const activeTeams = ['a', 'b', 'c', 'd'].slice(0, Math.max(2, teamCount));

  // Get the current player's team for "Team Full" display
  const myPlayer = lobbyPlayers[playerId];
  const myTeam = myPlayer?.team || 'a';

  return (
    <div className="deployed-forces">
      <h3 className="grim-header grim-header--left grim-header--sm">Deployed Forces</h3>
      <div className="deployed-forces-grid">
        {activeTeams.map((teamKey) => {
          const teamInfo = TEAM_CONFIG[teamKey];
          const members = teams[teamKey];
          const slotInfo = teamSlots?.[teamKey];
          const used = slotInfo?.used ?? members.length;
          const max = slotInfo?.max ?? 5;
          const isFull = used >= max;
          return (
            <div key={teamKey} className={`deployed-team ${isFull ? 'deployed-team--full' : ''}`} data-team={teamKey} style={{ borderColor: teamInfo.color }}>
              <div className="deployed-team-header" style={{ color: teamInfo.color }}>
                {teamInfo.label} ({teamInfo.colorName})
                <span className={`deployed-team-count ${isFull ? 'deployed-team-count--full' : ''}`}>
                  {used}/{max}
                </span>
              </div>
              {isFull && teamKey === myTeam && (
                <div className="deployed-team-full-indicator">Team Full</div>
              )}
              <div className="deployed-team-members">
                {members.length === 0 ? (
                  <div className="deployed-team-empty">— empty —</div>
                ) : (
                  members.map((member) => {
                    const cls = member.class_id && availableClasses[member.class_id];
                    const isYou = member.pid === playerId;
                    const isHuman = member.unit_type !== 'ai';
                    const isHeroAlly = !isHuman && member.owner_username;
                    return (
                      <div key={member.pid} className={`deployed-unit ${isYou ? 'deployed-unit--you' : ''}`}>
                        <span className="deployed-unit-icon">
                          {isHuman ? '★' : '🤖'}
                        </span>
                        <span className="deployed-unit-name">
                          {member.username}
                          {isYou && <span className="deployed-unit-you">(you)</span>}
                          {isHeroAlly && (
                            <span className="deployed-unit-owner">({member.owner_username}'s hero)</span>
                          )}
                        </span>
                        {cls && (
                          <span className="deployed-unit-class" style={{ color: cls.color }}>
                            {cls.name}
                          </span>
                        )}
                        {/* Team selection dropdown — only for yourself */}
                        {isYou && (
                          <select
                            className="team-select team-select--small"
                            value={member.team || 'a'}
                            onChange={(e) => onTeamChange(e.target.value)}
                            disabled={isReady}
                          >
                            {activeTeams.map((tk) => (
                              <option key={tk} value={tk}>{TEAM_CONFIG[tk].label}</option>
                            ))}
                          </select>
                        )}
                        <span className={`deployed-unit-status ${member.is_ready ? 'deployed-unit-status--ready' : ''}`}>
                          {member.is_ready ? '⚔' : '○'}
                        </span>
                      </div>
                    );
                  })
                )}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
