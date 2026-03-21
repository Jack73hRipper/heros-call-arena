/**
 * DevOverlayPanel — Floating developer overlay panel for dungeon observation.
 *
 * Displays toggle buttons for fog, free camera, grid coords, room bounds, etc.
 * Includes a unit inspector that shows detailed stats for a clicked unit,
 * plus equipment and inventory sections for debugging AI hero loadouts.
 * Styled to match the grimdark theme of the game.
 */
import React, { useState } from 'react';

const RARITY_COLORS = {
  common: '#999',
  magic: '#6688ff',
  rare: '#ffd700',
  epic: '#bb66ff',
  unique: '#ff8800',
  set: '#00cc66',
};

function getRarityColor(rarity) {
  return RARITY_COLORS[(rarity || 'common').toLowerCase()] || '#999';
}

function formatStatBonuses(bonuses) {
  if (!bonuses || typeof bonuses !== 'object') return null;
  const lines = [];
  const labels = {
    attack_damage: 'ATK', ranged_damage: 'RATK', armor: 'ARM', max_hp: 'HP',
    crit_chance: 'Crit%', crit_damage: 'CritDmg', dodge_chance: 'Dodge%',
    damage_reduction_pct: 'DR%', hp_regen: 'Regen', life_on_hit: 'LoH',
    cooldown_reduction_pct: 'CDR%', skill_damage_pct: 'SkillDmg%', thorns: 'Thorns',
    gold_find_pct: 'GF%', magic_find_pct: 'MF%', armor_pen: 'ArPen',
    attack_bonus: 'ATK', ranged_bonus: 'RATK', armor_bonus: 'ARM', max_hp_bonus: 'HP',
  };
  for (const [key, val] of Object.entries(bonuses)) {
    if (val && val !== 0) {
      const label = labels[key] || key;
      const isPercent = key.includes('pct') || key.includes('chance') || key === 'crit_damage';
      const display = isPercent ? `${(val * 100).toFixed(0)}%` : (val > 0 ? `+${val}` : val);
      lines.push(`${display} ${label}`);
    }
  }
  return lines.length > 0 ? lines.join(', ') : null;
}

function EquipmentSlot({ slotName, item }) {
  if (!item) {
    return (
      <div className="dev-equip-slot empty">
        <span className="dev-equip-slot-label">{slotName}:</span>
        <span className="dev-equip-empty">— empty —</span>
      </div>
    );
  }

  const rarity = item.rarity || 'common';
  const color = getRarityColor(rarity);
  const name = item.display_name || item.name || item.item_id || 'Unknown';
  const category = item.weapon_category || item.armor_category || '';
  const affixes = (item.affixes || []).map(a => a.name).filter(Boolean).join(', ');
  const stats = formatStatBonuses(item.stat_bonuses);
  const setName = item.set_id ? item.set_id.replace(/_/g, ' ') : null;

  return (
    <div className="dev-equip-slot">
      <span className="dev-equip-slot-label">{slotName}:</span>
      <span className="dev-equip-name" style={{ color }}>{name}</span>
      <span className="dev-equip-rarity" style={{ color }}>[{rarity}]</span>
      {category && <span className="dev-equip-category">{category}</span>}
      {stats && <div className="dev-equip-stats">{stats}</div>}
      {affixes && <div className="dev-equip-affixes">Affixes: {affixes}</div>}
      {setName && <div className="dev-equip-set">Set: {setName}</div>}
    </div>
  );
}

function InventoryItem({ item, index }) {
  const rarity = item.rarity || 'common';
  const color = getRarityColor(rarity);
  const name = item.display_name || item.name || item.item_id || 'Unknown';
  const isConsumable = item.item_type === 'consumable' || item.item_type === 'CONSUMABLE';

  return (
    <div className={`dev-inv-item ${isConsumable ? 'consumable' : ''}`}>
      <span className="dev-inv-index">{index}.</span>
      <span className="dev-inv-name" style={{ color }}>{name}</span>
      <span className="dev-inv-rarity" style={{ color }}>[{rarity}]</span>
      {isConsumable && <span className="dev-inv-consumable">⚗</span>}
    </div>
  );
}

export default function DevOverlayPanel({
  devMode,
  fogDisabled, toggleFog,
  freeCam, toggleFreeCam, resetCamera,
  showGridCoords, toggleGridCoords,
  showAllUnits, toggleShowUnits,
  showRoomBounds, toggleRoomBounds,
  showSpawns, toggleSpawns,
  inspectMode, toggleInspectMode,
  inspectedUnit, inspectedInventory, inspectUnit,
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

  const [showEquipment, setShowEquipment] = useState(true);
  const [showInventory, setShowInventory] = useState(true);

  const equipment = inspectedInventory?.equipment || {};
  const inventory = inspectedInventory?.inventory || [];

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

            {/* Equipment Section */}
            <div className="dev-equip-section">
              <div
                className="dev-section-header"
                onClick={() => setShowEquipment(prev => !prev)}
              >
                <span>⚔ Equipment</span>
                <span className="dev-section-toggle">{showEquipment ? '▾' : '▸'}</span>
              </div>
              {showEquipment && (
                <div className="dev-equip-list">
                  {inspectedInventory ? (
                    <>
                      <EquipmentSlot slotName="Weapon" item={equipment.weapon} />
                      <EquipmentSlot slotName="Armor" item={equipment.armor} />
                      <EquipmentSlot slotName="Accessory" item={equipment.accessory} />
                      {inspectedUnit.active_set_bonuses && inspectedUnit.active_set_bonuses.length > 0 && (
                        <div className="dev-equip-set-bonuses">
                          <span className="dev-label">Set Bonuses:</span>
                          {inspectedUnit.active_set_bonuses.map((sb, i) => (
                            <div key={i} className="dev-set-bonus">{sb.set_name || sb.set_id}: {sb.pieces}pc</div>
                          ))}
                        </div>
                      )}
                    </>
                  ) : (
                    <div className="dev-equip-loading">Loading...</div>
                  )}
                </div>
              )}
            </div>

            {/* Inventory Section */}
            <div className="dev-inv-section">
              <div
                className="dev-section-header"
                onClick={() => setShowInventory(prev => !prev)}
              >
                <span>🎒 Inventory ({inventory.length}/10)</span>
                <span className="dev-section-toggle">{showInventory ? '▾' : '▸'}</span>
              </div>
              {showInventory && (
                <div className="dev-inv-list">
                  {inspectedInventory ? (
                    inventory.length > 0 ? (
                      inventory.map((item, i) => (
                        <InventoryItem key={item.instance_id || item.item_id || i} item={item} index={i + 1} />
                      ))
                    ) : (
                      <div className="dev-equip-empty">— empty bag —</div>
                    )
                  ) : (
                    <div className="dev-equip-loading">Loading...</div>
                  )}
                </div>
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
