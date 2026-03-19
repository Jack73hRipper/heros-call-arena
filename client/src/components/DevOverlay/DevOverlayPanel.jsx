/**
 * DevOverlayPanel — Floating developer overlay panel for dungeon observation.
 *
 * Displays toggle buttons for fog, free camera, grid coords, room bounds, etc.
 * Includes a unit inspector that shows detailed stats for a clicked unit.
 * Styled to match the grimdark theme of the game.
 */
import React from 'react';

export default function DevOverlayPanel({
  devMode,
  fogDisabled, toggleFog,
  freeCam, toggleFreeCam, resetCamera,
  showGridCoords, toggleGridCoords,
  showAllUnits, toggleShowUnits,
  showRoomBounds, toggleRoomBounds,
  showSpawns, toggleSpawns,
  inspectMode, toggleInspectMode,
  inspectedUnit, inspectUnit,
  freeCamOffset,
  hoveredTile,
  currentTurn,
  players,
  dungeonRooms,
}) {
  if (!devMode) return null;

  const allPlayers = Object.values(players || {});
  const alive = allPlayers.filter(p => p.is_alive !== false && !p.extracted);
  const enemyCount = alive.filter(p => p.unit_type === 'enemy').length;
  const allyCount = alive.length - enemyCount;
  const bossCount = alive.filter(p => p.is_boss).length;
  const rareCount = alive.filter(p => p.monster_rarity === 'rare' || p.monster_rarity === 'super_unique').length;
  const roomCount = (dungeonRooms || []).length;

  return (
    <>
      {/* Top-center dev mode banner */}
      <div className="dev-mode-banner">DEV MODE</div>

      <div className="dev-overlay-panel">
        <div className="dev-overlay-header">
          <span className="dev-overlay-title">DEV OVERLAY</span>
          <span className="dev-overlay-turn">Turn {currentTurn || 0}</span>
        </div>

        {/* Live stats */}
        <div className="dev-overlay-stats">
          <span>Units: {alive.length} ({allyCount}A / {enemyCount}E)</span>
          {bossCount > 0 && <span>Bosses: {bossCount} | Elites: {rareCount}</span>}
          <span>Rooms: {roomCount}</span>
          {hoveredTile && <span>Cursor: ({hoveredTile.x}, {hoveredTile.y})</span>}
          {freeCam && <span>Camera: ({Math.round(freeCamOffset.x)}, {Math.round(freeCamOffset.y)})</span>}
        </div>

        {/* Toggle buttons */}
        <div className="dev-overlay-toggles">
          <button
            className={`dev-toggle ${fogDisabled ? 'active' : ''}`}
            onClick={toggleFog}
            title="Remove all fog of war — reveals entire map"
          >
            {fogDisabled ? '👁 Fog OFF' : '🌫 Fog ON'}
          </button>

          <button
            className={`dev-toggle ${showAllUnits ? 'active' : ''}`}
            onClick={toggleShowUnits}
            title="Show all units regardless of fog of war"
          >
            {showAllUnits ? '👤 All Units' : '👤 FOV Only'}
          </button>

          <button
            className={`dev-toggle ${freeCam ? 'active' : ''}`}
            onClick={toggleFreeCam}
            title="Detach camera — pan with arrow keys"
          >
            {freeCam ? '🎥 Free Cam' : '📍 Locked'}
          </button>

          {freeCam && (
            <button className="dev-toggle" onClick={resetCamera} title="Snap camera back to player">
              ↩ Reset Cam
            </button>
          )}

          <button
            className={`dev-toggle ${showGridCoords ? 'active' : ''}`}
            onClick={toggleGridCoords}
            title="Show (x,y) coordinates on each tile"
          >
            {showGridCoords ? '# Coords ON' : '# Coords OFF'}
          </button>

          <button
            className={`dev-toggle ${showRoomBounds ? 'active' : ''}`}
            onClick={toggleRoomBounds}
            title="Highlight dungeon room boundaries with archetype labels"
          >
            {showRoomBounds ? '⬜ Rooms ON' : '⬜ Rooms OFF'}
          </button>

          <button
            className={`dev-toggle ${showSpawns ? 'active' : ''}`}
            onClick={toggleSpawns}
            title="Highlight spawn point tiles"
          >
            {showSpawns ? '⚑ Spawns ON' : '⚑ Spawns OFF'}
          </button>

          <button
            className={`dev-toggle ${inspectMode ? 'active' : ''}`}
            onClick={toggleInspectMode}
            title="Click any unit to inspect stats — disables gameplay clicks while active"
          >
            {inspectMode ? '🔍 Inspect ON' : '🔍 Inspect OFF'}
          </button>
        </div>

        {/* Unit Inspector */}
        {inspectedUnit && (
          <div className="dev-inspect-panel">
            <div className="dev-inspect-header">
              <span>{inspectedUnit.display_name || inspectedUnit.username}</span>
              <button className="dev-inspect-close" onClick={() => inspectUnit(null)}>✕</button>
            </div>
            <div className="dev-inspect-body">
              <div><span className="dev-label">ID:</span> {inspectedUnit.id}</div>
              <div><span className="dev-label">Class:</span> {inspectedUnit.class_id}</div>
              <div><span className="dev-label">HP:</span> {inspectedUnit.hp} / {inspectedUnit.max_hp}</div>
              <div><span className="dev-label">Pos:</span> ({inspectedUnit.position?.x}, {inspectedUnit.position?.y})</div>
              <div><span className="dev-label">Team:</span> {inspectedUnit.team}</div>
              <div><span className="dev-label">Type:</span> {inspectedUnit.unit_type || 'player'}</div>
              {inspectedUnit.enemy_type && (
                <div><span className="dev-label">Enemy:</span> {inspectedUnit.enemy_type}</div>
              )}
              {inspectedUnit.monster_rarity && (
                <div><span className="dev-label">Rarity:</span> {inspectedUnit.monster_rarity}</div>
              )}
              {inspectedUnit.champion_type && (
                <div><span className="dev-label">Champion:</span> {inspectedUnit.champion_type}</div>
              )}
              {inspectedUnit.is_boss && <div className="dev-tag boss">BOSS</div>}
              {inspectedUnit.ai_stance && (
                <div><span className="dev-label">Stance:</span> {inspectedUnit.ai_stance}</div>
              )}
              {inspectedUnit.active_buffs && inspectedUnit.active_buffs.length > 0 && (
                <div><span className="dev-label">Buffs:</span> {inspectedUnit.active_buffs.map(b => b.name || b.type || b.buff_type).join(', ')}</div>
              )}
              {inspectedUnit.affix_ids && inspectedUnit.affix_ids.length > 0 && (
                <div><span className="dev-label">Affixes:</span> {inspectedUnit.affix_ids.join(', ')}</div>
              )}
              {inspectedUnit.attack_power != null && (
                <div><span className="dev-label">ATK:</span> {inspectedUnit.attack_power}</div>
              )}
              {inspectedUnit.defense != null && (
                <div><span className="dev-label">DEF:</span> {inspectedUnit.defense}</div>
              )}
            </div>
          </div>
        )}

        <div className="dev-overlay-hint">
          Press <kbd>`</kbd> to close{inspectMode ? ' · 🔍 Click unit to inspect' : ''}
        </div>
      </div>
    </>
  );
}
