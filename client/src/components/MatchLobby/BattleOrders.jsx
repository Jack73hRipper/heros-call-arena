import React from 'react';

/**
 * BattleOrders — Host config panel for the new MatchLobby (Phase L1).
 *
 * Shows map selection (PvE only — PvP and PvPvE have fixed maps),
 * theme dropdown, and PvPvE-specific config controls.
 * Non-hosts see read-only labels.
 */

const DUNGEON_THEMES = [
  { id: '',                    label: '🎲 Random Theme' },
  { id: 'bleeding_catacombs',  label: '🩸 Bleeding Catacombs' },
  { id: 'ashen_undercroft',    label: '🔥 Ashen Undercroft' },
  { id: 'drowned_sanctum',    label: '🌊 Drowned Sanctum' },
  { id: 'hollowed_cathedral',  label: '⛪ Hollowed Cathedral' },
  { id: 'iron_depths',         label: '⚙️ Iron Depths' },
  { id: 'forgotten_cellar',    label: '🪨 Forgotten Cellar' },
  { id: 'pale_ossuary',        label: '🦴 Pale Ossuary' },
  { id: 'silent_vault',        label: '🔇 Silent Vault' },
  { id: 'fungal_grotto',       label: '🍄 Fungal Grotto' },
  { id: 'frozen_crypt',        label: '❄️ Frozen Crypt' },
  { id: 'cursed_shrine',       label: '🕷️ Cursed Shrine' },
];

const PVPVE_GRID_SIZES = [
  { value: 6, label: 'Medium (6×6)' },
  { value: 8, label: 'Large (8×8)' },
  { value: 10, label: 'XL (10×10)' },
];

const PVPVE_DENSITY_LABELS = [
  { value: 0.3, label: 'Low' },
  { value: 0.5, label: 'Medium' },
  { value: 0.7, label: 'High' },
];

const TEAM_COLORS = {
  a: { label: 'Team A', color: '#4a8fd0' },
  b: { label: 'Team B', color: '#e04040' },
  c: { label: 'Team C', color: '#40c040' },
  d: { label: 'Team D', color: '#d4a017' },
};

const PVPVE_TEAM_KEYS_ORDER = ['a', 'b', 'c', 'd'];

export default function BattleOrders({
  config,
  lobbyMode,
  selectedMap,
  isHost,
  isReady,
  onMapChange,
  onConfigChange,
  availableMaps,
}) {
  const showMapDropdown = lobbyMode === 'pve' && availableMaps.length > 1;
  const showTheme = (lobbyMode === 'pve' && selectedMap === 'wfc_dungeon') || lobbyMode === 'pvpve';
  const showPvpveConfig = lobbyMode === 'pvpve';

  return (
    <div className="battle-orders">
      <h3 className="grim-header grim-header--left grim-header--sm">
        Battle Orders {!isHost && <span className="config-readonly">(host controls)</span>}
      </h3>

      <div className="config-grid">
        {/* Map selector — PvE only (PvP = Arena Classic fixed, PvPvE = The Crucible fixed) */}
        {showMapDropdown && (
          <div className="config-row">
            <label>Map:</label>
            {isHost ? (
              <select
                className="war-room-select"
                value={selectedMap}
                onChange={(e) => onMapChange(e.target.value)}
                disabled={isReady}
              >
                {availableMaps.map((m) => (
                  <option key={m.id} value={m.id}>{m.label}</option>
                ))}
              </select>
            ) : (
              <span className="config-value">
                {availableMaps.find(m => m.id === selectedMap)?.label || selectedMap}
              </span>
            )}
          </div>
        )}

        {/* Fixed map display for PvP and PvPvE */}
        {lobbyMode === 'pvp' && (
          <>
            <div className="config-row">
              <label>Map:</label>
              <span className="config-value">Arena Classic</span>
            </div>
            <div className="config-row config-row--minimal">
              <span className="config-hint">Team assignment only — configure teams in Deployed Forces below.</span>
            </div>
          </>
        )}
        {lobbyMode === 'pvpve' && (
          <div className="config-row">
            <label>Map:</label>
            <span className="config-value">The Crucible (Procedural)</span>
          </div>
        )}

        {/* Theme selector — PvE: The Crypt only; PvPvE: always */}
        {showTheme && (
          <div className="config-row">
            <label>Dungeon Theme:</label>
            {isHost ? (
              <select
                className="war-room-select theme-select"
                value={config.theme_id || ''}
                onChange={(e) => onConfigChange({ theme_id: e.target.value || null })}
                disabled={isReady}
              >
                {DUNGEON_THEMES.map((t) => (
                  <option key={t.id} value={t.id}>{t.label}</option>
                ))}
              </select>
            ) : (
              <span className="config-value">
                {config.theme_id
                  ? (DUNGEON_THEMES.find(t => t.id === config.theme_id)?.label || config.theme_id)
                  : '🎲 Random Theme'}
              </span>
            )}
          </div>
        )}

        {/* ── PvPvE Config Block ── */}
        {showPvpveConfig && (
          <>
            <div className="config-row">
              <label>Total Teams: {config.pvpve_team_count ?? 2}</label>
              <span className="config-hint">How many competing teams in the dungeon</span>
              {isHost ? (
                <input
                  type="range" min="2" max="4"
                  value={config.pvpve_team_count ?? 2}
                  onChange={(e) => onConfigChange({ pvpve_team_count: Number(e.target.value) })}
                  disabled={isReady}
                />
              ) : (
                <span className="config-value">{config.pvpve_team_count ?? 2} teams</span>
              )}
            </div>

            <div className="config-row">
              <label>Monster Density:</label>
              <span className="config-hint">PVE enemies populating dungeon rooms</span>
              {isHost ? (
                <select
                  className="war-room-select"
                  value={config.pvpve_pve_density ?? 0.5}
                  onChange={(e) => onConfigChange({ pvpve_pve_density: Number(e.target.value) })}
                  disabled={isReady}
                >
                  {PVPVE_DENSITY_LABELS.map((d) => (
                    <option key={d.value} value={d.value}>{d.label}</option>
                  ))}
                </select>
              ) : (
                <span className="config-value">
                  {PVPVE_DENSITY_LABELS.find(d => d.value === (config.pvpve_pve_density ?? 0.5))?.label || 'Medium'}
                </span>
              )}
            </div>

            <div className="config-row">
              <label>Grid Size:</label>
              {isHost ? (
                <select
                  className="war-room-select"
                  value={config.pvpve_grid_size ?? 8}
                  onChange={(e) => onConfigChange({ pvpve_grid_size: Number(e.target.value) })}
                  disabled={isReady}
                >
                  {PVPVE_GRID_SIZES.map((g) => (
                    <option key={g.value} value={g.value}>{g.label}</option>
                  ))}
                </select>
              ) : (
                <span className="config-value">
                  {PVPVE_GRID_SIZES.find(g => g.value === (config.pvpve_grid_size ?? 8))?.label || 'Large (8×8)'}
                </span>
              )}
            </div>

            <div className="config-row">
              <label>Boss Enabled:</label>
              {isHost ? (
                <button
                  className={`war-room-mode-btn ${(config.pvpve_boss_enabled !== false) ? 'war-room-mode-btn--active' : ''}`}
                  onClick={() => onConfigChange({ pvpve_boss_enabled: !(config.pvpve_boss_enabled !== false) })}
                  disabled={isReady}
                >
                  {(config.pvpve_boss_enabled !== false) ? '💀 Boss On' : '○ Boss Off'}
                </button>
              ) : (
                <span className="config-value">{(config.pvpve_boss_enabled !== false) ? '💀 Boss On' : '○ Boss Off'}</span>
              )}
            </div>

            {/* AI Rival Teams */}
            <div className="config-row">
              <label>AI Rival Teams: {config.pvpve_ai_team_count ?? 0}</label>
              <span className="config-hint">Fill empty team slots with AI-controlled rival squads</span>
              {isHost ? (
                <input
                  type="range" min="0" max={Math.max(0, (config.pvpve_team_count ?? 2) - 1)}
                  value={config.pvpve_ai_team_count ?? 0}
                  onChange={(e) => onConfigChange({ pvpve_ai_team_count: Number(e.target.value) })}
                  disabled={isReady}
                />
              ) : (
                <span className="config-value">{config.pvpve_ai_team_count ?? 0}</span>
              )}
            </div>

            {/* AI Team Sizes */}
            {(config.pvpve_ai_team_count ?? 0) > 0 && (
              <div className="config-row config-row--column">
                <label>AI Team Sizes:</label>
                <div className="ai-class-slots">
                  {Array.from({ length: config.pvpve_ai_team_count ?? 0 }, (_, teamIdx) => {
                    const teamKey = PVPVE_TEAM_KEYS_ORDER[teamIdx + 1];
                    const teamSizes = config.pvpve_ai_team_sizes || [];
                    const currentSize = teamSizes[teamIdx] ?? 3;
                    return (
                      <div key={`ai-team-${teamIdx}`} className="ai-class-slot">
                        <span className="ai-class-slot-label" style={{ color: TEAM_COLORS[teamKey]?.color || '#aaa' }}>
                          {TEAM_COLORS[teamKey]?.label || `Team ${teamKey?.toUpperCase()}`}
                        </span>
                        {isHost ? (
                          <input
                            type="range" min="1" max="5"
                            value={currentSize}
                            onChange={(e) => {
                              const updated = [...(config.pvpve_ai_team_sizes || [])];
                              while (updated.length <= teamIdx) updated.push(3);
                              updated[teamIdx] = Number(e.target.value);
                              onConfigChange({ pvpve_ai_team_sizes: updated });
                            }}
                            disabled={isReady}
                            className="pvpve-team-size-slider"
                          />
                        ) : null}
                        <span className="config-value">{currentSize} units</span>
                      </div>
                    );
                  })}
                </div>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}
