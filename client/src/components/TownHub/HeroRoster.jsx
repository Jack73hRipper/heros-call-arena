import React, { useState } from 'react';
import { useGameState, useGameDispatch } from '../../context/GameStateContext';
import HeroDetailPanel from './HeroDetailPanel';
import HeroSprite from './HeroSprite';
import { formatStatBonuses } from '../../utils/itemUtils';

/**
 * HeroRoster — displays owned heroes with stats and gear.
 * Use the "Manage Gear" button to open the gear management panel.
 * "Select for Dungeon" button toggles hero selection (up to 4).
 *
 * Phase 4E-3: Consumes stable 4E-1 REST API roster data.
 * Phase 5 Feature 7: Click-to-manage gear integration.
 * Multi-hero: Supports selecting up to 4 heroes for dungeon runs.
 */
export default function HeroRoster({ availableClasses, onSelectHero }) {
  const gameState = useGameState();
  const dispatch = useGameDispatch();
  const [inspectedHeroId, setInspectedHeroId] = useState(null);
  const [tooltip, setTooltip] = useState(null); // { item, x, y }

  const heroes = gameState.heroes || [];
  const selectedHeroIds = gameState.selectedHeroIds || [];
  const aliveHeroes = heroes.filter(h => h.is_alive);
  const fallenHeroes = heroes.filter(h => !h.is_alive);

  const getClassDef = (classId) => availableClasses?.[classId] || {};

  const getEquipmentSummary = (equipment) => {
    if (!equipment || typeof equipment !== 'object') return [];
    const items = [];
    for (const [slot, item] of Object.entries(equipment)) {
      if (item && item.name) {
        items.push({ slot, name: item.name, rarity: item.rarity || 'common', item });
      }
    }
    return items;
  };

  const handleEquipTagEnter = (e, item) => {
    const rect = e.currentTarget.getBoundingClientRect();
    setTooltip({ item, x: rect.left + rect.width / 2, y: rect.top });
  };

  const handleEquipTagLeave = () => {
    setTooltip(null);
  };

  const handleSelect = (heroId) => {
    dispatch({ type: 'SELECT_HERO', payload: heroId });
    if (onSelectHero) onSelectHero(heroId);
  };

  return (
    <div className="hero-roster">
      <h3>Hero Roster ({aliveHeroes.length} / 10)</h3>
      <p className="party-counter" style={{ visibility: selectedHeroIds.length > 0 ? 'visible' : 'hidden' }}>
        Party: {selectedHeroIds.length}/4 selected
      </p>

      {aliveHeroes.length === 0 && fallenHeroes.length === 0 && (
        <p className="town-placeholder">No heroes yet. Visit the Hiring Hall to recruit!</p>
      )}

      {aliveHeroes.length === 0 && fallenHeroes.length > 0 && (
        <p className="town-placeholder">All heroes have fallen... Visit the Hiring Hall.</p>
      )}

      {/* Alive heroes */}
      {aliveHeroes.length > 0 && (
        <div className="roster-hero-grid">
          {aliveHeroes.map((hero) => {
            const classDef = getClassDef(hero.class_id);
            const isSelected = selectedHeroIds.includes(hero.hero_id);
            const selectionIndex = selectedHeroIds.indexOf(hero.hero_id);
            const equipItems = getEquipmentSummary(hero.equipment);
            const invCount = (hero.inventory || []).length;
            const canSelect = isSelected || selectedHeroIds.length < 4;

            return (
              <div
                key={hero.hero_id}
                className={`roster-hero-card ${isSelected ? 'roster-hero-selected' : ''}`}
                style={{ borderColor: isSelected ? (classDef.color || '#e0a040') : undefined }}
              >
                <div className="hero-card-header">
                  <HeroSprite
                    classId={hero.class_id}
                    variant={hero.sprite_variant || 1}
                    size={64}
                    className="hero-card-sprite"
                  />
                  <div className="hero-card-name-block">
                    <strong className="hero-name">{hero.name}</strong>
                    <span className="hero-class-label" style={{ color: classDef.color || '#aaa' }}>
                      {classDef.name || hero.class_id}
                    </span>
                  </div>
                  {isSelected && <span className="selected-badge">✓ #{selectionIndex + 1}</span>}
                </div>

                <div className="hero-card-stats">
                  <div className="hero-stat-row">
                    <span className="hero-stat-label">HP</span>
                    <span className="hero-stat-value">{hero.stats.max_hp}</span>
                  </div>
                  <div className="hero-stat-row">
                    <span className="hero-stat-label">Melee</span>
                    <span className="hero-stat-value">{hero.stats.attack_damage}</span>
                  </div>
                  <div className="hero-stat-row">
                    <span className="hero-stat-label">Ranged</span>
                    <span className="hero-stat-value">{hero.stats.ranged_damage}</span>
                  </div>
                  <div className="hero-stat-row">
                    <span className="hero-stat-label">Armor</span>
                    <span className="hero-stat-value">{hero.stats.armor}</span>
                  </div>
                  <div className="hero-stat-row">
                    <span className="hero-stat-label">Vision</span>
                    <span className="hero-stat-value">{hero.stats.vision_range}</span>
                  </div>
                </div>

                {/* Equipment preview */}
                {equipItems.length > 0 && (
                  <div className="hero-card-equipment">
                    {equipItems.map((eq) => (
                      <span
                        key={eq.slot}
                        className={`hero-equip-tag rarity-${eq.rarity}`}
                        onMouseEnter={(e) => handleEquipTagEnter(e, eq.item)}
                        onMouseLeave={handleEquipTagLeave}
                      >
                        {eq.name}
                      </span>
                    ))}
                  </div>
                )}

                {/* Inventory count + tracking */}
                <div className="hero-card-meta">
                  {invCount > 0 && <span className="hero-inv-count">{invCount}/10 items</span>}
                  {hero.matches_survived > 0 && (
                    <span className="hero-track">{hero.matches_survived} runs</span>
                  )}
                  {hero.enemies_killed > 0 && (
                    <span className="hero-track">{hero.enemies_killed} kills</span>
                  )}
                </div>

                <div className="hero-card-footer">
                  <button
                    className="btn-manage-gear"
                    onClick={() => setInspectedHeroId(hero.hero_id)}
                  >
                    Manage Gear
                  </button>
                  <button
                    className={`btn-select-hero ${isSelected ? 'btn-selected' : ''} ${!canSelect ? 'btn-disabled' : ''}`}
                    onClick={() => { if (canSelect) handleSelect(hero.hero_id); }}
                    disabled={!canSelect}
                  >
                    {isSelected ? `✓ Selected (#${selectionIndex + 1})` : selectedHeroIds.length >= 4 ? 'Party Full (4/4)' : 'Select for Dungeon'}
                  </button>
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* Fallen heroes */}
      {fallenHeroes.length > 0 && (
        <div className="fallen-heroes-section">
          <h4 className="fallen-header">Fallen Heroes ({fallenHeroes.length})</h4>
          <div className="fallen-hero-list">
            {fallenHeroes.map((hero) => {
              const classDef = getClassDef(hero.class_id);
              return (
                <div key={hero.hero_id} className="fallen-hero-card">
                  <HeroSprite
                    classId={hero.class_id}
                    variant={hero.sprite_variant || 1}
                    size={36}
                    grayscale={true}
                    className="fallen-hero-sprite"
                  />
                  <span className="fallen-hero-name">{hero.name}</span>
                  <span className="fallen-hero-class">{classDef.name || hero.class_id}</span>
                  {hero.enemies_killed > 0 && (
                    <span className="fallen-hero-kills">{hero.enemies_killed} kills</span>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      )}
      {/* Gear Tooltip (fixed position, follows mouse) */}
      {tooltip && tooltip.item && (
        <div
          className="roster-gear-tooltip"
          style={{
            position: 'fixed',
            left: tooltip.x,
            top: tooltip.y,
            transform: 'translate(-50%, -100%) translateY(-8px)',
            zIndex: 9999,
            pointerEvents: 'none',
          }}
        >
          <div className={`gear-tooltip rarity-border-${tooltip.item.rarity || 'common'}`}>
            <div className={`gear-tooltip-name rarity-${tooltip.item.rarity || 'common'}`}>
              {tooltip.item.name}
            </div>
            <div className="gear-tooltip-type">
              {tooltip.item.rarity || 'common'} {tooltip.item.item_type}
              {tooltip.item.equip_slot ? ` — ${tooltip.item.equip_slot}` : ''}
            </div>
            {formatStatBonuses(tooltip.item.stat_bonuses).length > 0 && (
              <div className="gear-tooltip-stats">
                {formatStatBonuses(tooltip.item.stat_bonuses).map((s, i) => (
                  <span key={i}>{s}</span>
                ))}
              </div>
            )}
            {tooltip.item.description && (
              <div className="gear-tooltip-desc">{tooltip.item.description}</div>
            )}
            {tooltip.item.sell_value > 0 && (
              <div className="gear-tooltip-sell">Sell: {tooltip.item.sell_value}g</div>
            )}
          </div>
        </div>
      )}
      {/* Hero Detail Panel (gear management overlay) */}
      {inspectedHeroId && (() => {
        const inspectedHero = heroes.find(h => h.hero_id === inspectedHeroId);
        if (!inspectedHero || !inspectedHero.is_alive) return null;
        return (
          <HeroDetailPanel
            hero={inspectedHero}
            availableClasses={availableClasses}
            onClose={() => setInspectedHeroId(null)}
            onSelectHero={onSelectHero}
          />
        );
      })()}
    </div>
  );
}
