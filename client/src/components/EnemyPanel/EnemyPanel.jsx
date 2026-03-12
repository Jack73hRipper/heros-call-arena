import React, { useCallback, useMemo } from 'react';
import { useGameState, useGameDispatch } from '../../context/GameStateContext';

/**
 * EnemyPanel — Displays hostile units currently visible in the player's FOV.
 * Mirrors PartyPanel structure but for enemies.
 * Left-click to soft-select (target-first casting). Right-click to auto-target (pursuit).
 * Sorted by distance (nearest first), bosses pinned to top.
 *
 * Phase 18E (E7): Enhanced with rarity badge, champion type tag, and affix icon row.
 */

// Phase 18E: Rarity display config
const RARITY_COLORS = {
  normal: '#ffffff',
  champion: '#6688ff',
  rare: '#ffcc00',
  super_unique: '#cc66ff',
};

const RARITY_LABELS = {
  normal: null,          // No badge for normal
  champion: 'Champion',
  rare: 'Rare',
  super_unique: 'Super Unique',
};

// Phase 18E: Champion type display config
const CHAMPION_TYPE_LABELS = {
  berserker:  { icon: '⚔', label: 'Berserker' },
  fanatic:    { icon: '⚡', label: 'Fanatic' },
  ghostly:    { icon: '👻', label: 'Ghostly' },
  resilient:  { icon: '🛡', label: 'Resilient' },
  possessed:  { icon: '💀', label: 'Possessed' },
};

// Phase 18E: Affix display config (icon + short description for tooltip)
const AFFIX_DISPLAY = {
  extra_strong:     { icon: '💪', label: 'Extra Strong', desc: 'Increased damage' },
  extra_fast:       { icon: '⚡', label: 'Extra Fast', desc: 'Increased speed' },
  fire_enchanted:   { icon: '🔥', label: 'Fire Enchanted', desc: 'Fire damage on hit; explodes on death' },
  cold_enchanted:   { icon: '❄', label: 'Cold Enchanted', desc: 'Cold damage; slows targets' },
  stone_skin:       { icon: '🪨', label: 'Stone Skin', desc: 'Greatly increased armor' },
  thorns:           { icon: '🌵', label: 'Thorns', desc: 'Reflects damage to attackers' },
  might_aura:       { icon: '🔴', label: 'Might Aura', desc: 'Boosts nearby ally damage' },
  conviction_aura:  { icon: '🟣', label: 'Conviction Aura', desc: 'Reduces nearby enemy armor' },
  shielded:         { icon: '🛡', label: 'Shielded', desc: 'Ward charges absorb damage' },
  teleporter:       { icon: '✦', label: 'Teleporter', desc: 'Periodically teleports' },
  regenerating:     { icon: '💚', label: 'Regenerating', desc: 'Regenerates HP over time' },
  cursed:           { icon: '☠', label: 'Cursed', desc: 'Debuffs attackers' },
  multishot:        { icon: '🏹', label: 'Multishot', desc: 'Ranged attacks hit multiple targets' },
  spectral_hit:     { icon: '👁', label: 'Spectral Hit', desc: 'Attacks ignore some armor' },
  mana_burn:        { icon: '🔮', label: 'Mana Burn', desc: 'Drains mana on hit' },
};

export default function EnemyPanel({ sendAction }) {
  const {
    players, playerId, visibleTiles,
    teamA, teamB, teamC, teamD,
    selectedTargetId, autoTargetId,
    activeUnitId,
  } = useGameState();
  const dispatch = useGameDispatch();

  const myPlayer = players[playerId];
  const myTeam = myPlayer?.team || 'a';
  const effectiveUnitId = activeUnitId || playerId;
  const activeUnit = players[effectiveUnitId];

  // Derive visible enemies from game state
  const visibleEnemies = useMemo(() => {
    if (!myPlayer) return [];
    const myPos = activeUnit?.position || myPlayer.position;

    const enemies = Object.entries(players)
      .filter(([id, p]) => {
        if (!p || p.team === myTeam) return false;
        if (p.is_alive === false) return false;
        // Must be in FOV (if FOV is active)
        if (visibleTiles && p.position && !visibleTiles.has(`${p.position.x},${p.position.y}`)) return false;
        return true;
      })
      .map(([id, p]) => {
        const dx = (p.position?.x || 0) - (myPos?.x || 0);
        const dy = (p.position?.y || 0) - (myPos?.y || 0);
        const distance = Math.sqrt(dx * dx + dy * dy);
        return { id, ...p, distance };
      });

    // Sort: bosses first, then by distance (nearest first)
    enemies.sort((a, b) => {
      if (a.is_boss && !b.is_boss) return -1;
      if (!a.is_boss && b.is_boss) return 1;
      return a.distance - b.distance;
    });

    return enemies;
  }, [players, myPlayer, activeUnit, myTeam, visibleTiles]);

  // Left-click: soft-select as target (for target-first casting)
  const handleLeftClick = useCallback((enemyId) => {
    dispatch({ type: 'SELECT_TARGET', payload: { targetId: enemyId } });
  }, [dispatch]);

  // Right-click: set auto-target for pursuit
  const handleRightClick = useCallback((e, enemyId) => {
    e.preventDefault();
    const unitId = activeUnitId || effectiveUnitId;
    sendAction({ type: 'set_auto_target', target_id: enemyId, unit_id: unitId });
    dispatch({ type: 'SELECT_TARGET', payload: { targetId: enemyId } });
  }, [activeUnitId, effectiveUnitId, sendAction, dispatch]);

  return (
    <div className="enemy-panel">
      <h3 className="enemy-panel-title">
        Hostiles
        <span className="enemy-count-badge" title={`${visibleEnemies.length} enemies in view`}>
          {visibleEnemies.length}
        </span>
      </h3>

      {visibleEnemies.length > 0 && (
        <div className="enemy-panel-hint">
          Left = Target · Right = Pursue
        </div>
      )}

      <div className="enemy-member-list">
        {visibleEnemies.length === 0 ? (
          <p className="enemy-panel-empty">No hostiles in view</p>
        ) : visibleEnemies.map((enemy) => {
          const hpPct = enemy.max_hp > 0 ? Math.max(0, enemy.hp / enemy.max_hp * 100) : 0;
          const isSelected = selectedTargetId === enemy.id;
          const isAutoTarget = autoTargetId === enemy.id;

          // Phase 18E (E7): Rarity display data
          const rarity = enemy.monster_rarity || 'normal';
          const rarityColor = RARITY_COLORS[rarity] || '#ffffff';
          const rarityLabel = RARITY_LABELS[rarity];
          const championInfo = enemy.champion_type ? CHAMPION_TYPE_LABELS[enemy.champion_type] : null;
          const affixes = enemy.affixes || [];
          // Use display_name if available (rares get generated names, super uniques get fixed names)
          const displayName = enemy.display_name || enemy.username;

          return (
            <div
              key={enemy.id}
              className={`enemy-member ${isSelected ? 'enemy-member-selected' : ''} ${isAutoTarget ? 'enemy-member-auto-target' : ''}`}
              style={rarity !== 'normal' ? { borderColor: `${rarityColor}33` } : undefined}
            >
              <button
                className="enemy-member-clickable"
                onClick={() => handleLeftClick(enemy.id)}
                onContextMenu={(e) => handleRightClick(e, enemy.id)}
                title={`Left-click to target ${displayName} · Right-click to pursue`}
              >
                <div className="enemy-member-info">
                  <span className="enemy-member-name" style={rarity !== 'normal' ? { color: rarityColor } : undefined}>
                    {enemy.is_boss && <span className="enemy-boss-badge" title="Boss">💀</span>}
                    {displayName}
                  </span>
                  {rarityLabel ? (
                    <span
                      className="enemy-rarity-badge"
                      style={{ color: rarityColor, borderColor: `${rarityColor}55` }}
                      title={`${rarityLabel} monster`}
                    >
                      {rarityLabel}
                    </span>
                  ) : (
                    <span className="enemy-member-class">{enemy.class_id || 'Enemy'}</span>
                  )}
                </div>

                {/* Phase 18E: Champion type tag */}
                {championInfo && (
                  <div className="enemy-champion-tag" title={`Champion type: ${championInfo.label}`}>
                    <span>{championInfo.icon}</span> {championInfo.label}
                  </div>
                )}

                <div className="enemy-member-hp-bar">
                  <div
                    className="enemy-member-hp-fill"
                    style={{
                      width: `${hpPct}%`,
                      backgroundColor: hpPct > 50 ? '#c04040' : hpPct > 25 ? '#ff6a00' : '#ff2020',
                    }}
                  />
                </div>

                {/* Phase 18E → Improved: Affix readout list with name + description */}
                {affixes.length > 0 && (
                  <div className="enemy-affix-list">
                    {affixes.map((affix) => {
                      const info = AFFIX_DISPLAY[affix];
                      return (
                        <div key={affix} className="enemy-affix-entry">
                          <span className="enemy-affix-entry-icon">{info ? info.icon : '◆'}</span>
                          <span className="enemy-affix-entry-text">
                            <span className="enemy-affix-entry-name">{info ? info.label : affix}</span>
                            {info && <span className="enemy-affix-entry-desc"> — {info.desc}</span>}
                          </span>
                        </div>
                      );
                    })}
                  </div>
                )}

                <div className="enemy-member-status">
                  <span className="enemy-member-hp-text">{enemy.hp}/{enemy.max_hp}</span>
                  <span className="enemy-member-distance" title="Distance">
                    {enemy.distance.toFixed(1)} tiles
                  </span>
                  {isAutoTarget && <span className="enemy-member-pursuit">⊕ PURSUIT</span>}
                  {isSelected && !isAutoTarget && <span className="enemy-member-targeted">◎ TARGET</span>}
                </div>
              </button>
            </div>
          );
        })}
      </div>
    </div>
  );
}
