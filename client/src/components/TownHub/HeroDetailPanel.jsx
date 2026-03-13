import React, { useState, useCallback } from 'react';
import { useGameState, useGameDispatch } from '../../context/GameStateContext';
import { apiFetch } from '../../utils/serverUrl';
import HeroSprite from './HeroSprite';
import { formatStatBonuses } from '../../utils/itemUtils';

/**
 * HeroDetailPanel — Full gear management UI for a single hero.
 *
 * Displays:
 * - Hero stats (base + equipment bonuses)
 * - 3 equipment slots (weapon, armor, accessory) — click to unequip
 * - 10-slot bag grid — click equippable to equip, click to transfer
 * - Transfer modal for moving items between heroes
 *
 * Phase 5 Feature 7: Town gear management system.
 */

const ITEM_ICONS = {
  weapon: 'W',
  armor: 'A',
  accessory: 'R',
  consumable: 'C',
};

const SLOT_LABELS = {
  weapon: 'Weapon',
  armor: 'Armor',
  accessory: 'Accessory',
};

const SLOT_ICONS = {
  weapon: 'W',
  armor: 'A',
  accessory: 'R',
};

function getEquipmentBonuses(equipment) {
  const totals = { attack_damage: 0, ranged_damage: 0, armor: 0, max_hp: 0 };
  if (!equipment || typeof equipment !== 'object') return totals;
  for (const item of Object.values(equipment)) {
    if (item?.stat_bonuses) {
      totals.attack_damage += item.stat_bonuses.attack_damage || 0;
      totals.ranged_damage += item.stat_bonuses.ranged_damage || 0;
      totals.armor += item.stat_bonuses.armor || 0;
      totals.max_hp += item.stat_bonuses.max_hp || 0;
    }
  }
  return totals;
}

/**
 * ItemTooltip — positioned tooltip for item hover.
 */
function ItemTooltip({ item, hint }) {
  if (!item) return null;
  const rarity = item.rarity || 'common';
  const stats = formatStatBonuses(item.stat_bonuses);

  return (
    <div className={`gear-tooltip rarity-border-${rarity}`}>
      <div className={`gear-tooltip-name rarity-${rarity}`}>
        {ITEM_ICONS[item.item_type] || '?'} {item.name}
      </div>
      <div className="gear-tooltip-type">
        {rarity} {item.item_type}{item.equip_slot ? ` — ${item.equip_slot}` : ''}
      </div>
      {stats.length > 0 && (
        <div className="gear-tooltip-stats">
          {stats.map((s, i) => <span key={i}>{s}</span>)}
        </div>
      )}
      {item.consumable_effect && (
        <div className="gear-tooltip-stats">
          {item.consumable_effect.type === 'heal' && (
            <span>Restores {item.consumable_effect.magnitude} HP</span>
          )}
          {item.consumable_effect.type === 'portal' && (
            <span>Teleports party out of dungeon</span>
          )}
        </div>
      )}
      {item.description && (
        <div className="gear-tooltip-desc">{item.description}</div>
      )}
      {item.sell_value > 0 && (
        <div className="gear-tooltip-sell">Sell: {item.sell_value}g</div>
      )}
      {hint && <div className="gear-tooltip-hint">{hint}</div>}
    </div>
  );
}

export default function HeroDetailPanel({ hero, availableClasses, onClose, onSelectHero }) {
  const gameState = useGameState();
  const dispatch = useGameDispatch();

  const [hoveredItem, setHoveredItem] = useState(null);
  const [transferItem, setTransferItem] = useState(null); // { index, item } for transfer modal
  const [actionFeedback, setActionFeedback] = useState(null);
  const [loading, setLoading] = useState(false);

  const classDef = availableClasses?.[hero.class_id] || {};
  const equipment = hero.equipment || {};
  const inventory = hero.inventory || [];
  const bonuses = getEquipmentBonuses(equipment);
  const isSelected = (gameState.selectedHeroIds || []).includes(hero.hero_id);
  const selectionIndex = (gameState.selectedHeroIds || []).indexOf(hero.hero_id);
  const canSelect = isSelected || (gameState.selectedHeroIds || []).length < 4;
  const bank = gameState.bank || [];
  const BANK_CAPACITY = 20;
  const bankFull = bank.length >= BANK_CAPACITY;

  // Other alive heroes for transfer
  const otherHeroes = (gameState.heroes || []).filter(
    h => h.is_alive && h.hero_id !== hero.hero_id
  );

  const showFeedback = (msg, isError = false) => {
    setActionFeedback({ msg, isError });
    setTimeout(() => setActionFeedback(null), 2500);
  };

  // ---------- Equip ----------
  const handleEquip = useCallback(async (itemIndex) => {
    if (loading) return;
    setLoading(true);
    try {
      const res = await apiFetch('/api/town/equip', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          username: gameState.username,
          hero_id: hero.hero_id,
          item_index: itemIndex,
        }),
      });
      const data = await res.json();
      if (res.ok) {
        dispatch({
          type: 'HERO_EQUIP',
          payload: {
            hero_id: hero.hero_id,
            equipment: data.equipment,
            inventory: data.inventory,
          },
        });
        showFeedback(data.message);
      } else {
        showFeedback(data.detail || 'Failed to equip', true);
      }
    } catch (err) {
      showFeedback('Connection error', true);
      console.error('[HeroDetailPanel] Equip error:', err);
    } finally {
      setLoading(false);
    }
  }, [loading, gameState.username, hero.hero_id, dispatch]);

  // ---------- Unequip ----------
  const handleUnequip = useCallback(async (slot) => {
    if (loading) return;
    setLoading(true);
    try {
      const res = await apiFetch('/api/town/unequip', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          username: gameState.username,
          hero_id: hero.hero_id,
          slot,
        }),
      });
      const data = await res.json();
      if (res.ok) {
        dispatch({
          type: 'HERO_UNEQUIP',
          payload: {
            hero_id: hero.hero_id,
            equipment: data.equipment,
            inventory: data.inventory,
          },
        });
        showFeedback(data.message);
      } else {
        showFeedback(data.detail || 'Failed to unequip', true);
      }
    } catch (err) {
      showFeedback('Connection error', true);
      console.error('[HeroDetailPanel] Unequip error:', err);
    } finally {
      setLoading(false);
    }
  }, [loading, gameState.username, hero.hero_id, dispatch]);

  // ---------- Transfer ----------
  const handleTransfer = useCallback(async (toHeroId) => {
    if (loading || !transferItem) return;
    setLoading(true);
    try {
      const res = await apiFetch('/api/town/transfer', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          username: gameState.username,
          from_hero_id: hero.hero_id,
          to_hero_id: toHeroId,
          item_index: transferItem.index,
        }),
      });
      const data = await res.json();
      if (res.ok) {
        dispatch({
          type: 'HERO_TRANSFER',
          payload: {
            from_hero_id: hero.hero_id,
            to_hero_id: toHeroId,
            from_inventory: data.from_inventory,
            to_inventory: data.to_inventory,
          },
        });
        showFeedback(data.message);
        setTransferItem(null);
      } else {
        showFeedback(data.detail || 'Failed to transfer', true);
      }
    } catch (err) {
      showFeedback('Connection error', true);
      console.error('[HeroDetailPanel] Transfer error:', err);
    } finally {
      setLoading(false);
    }
  }, [loading, transferItem, gameState.username, hero.hero_id, dispatch]);

  // ---------- Bank Deposit ----------
  const handleBankDeposit = useCallback(async (itemIndex) => {
    if (loading) return;
    setLoading(true);
    try {
      const res = await apiFetch('/api/town/bank/deposit', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          username: gameState.username,
          hero_id: hero.hero_id,
          item_index: itemIndex,
        }),
      });
      const data = await res.json();
      if (res.ok) {
        dispatch({
          type: 'BANK_DEPOSIT',
          payload: {
            hero_id: data.hero_id,
            inventory: data.inventory,
            bank: data.bank,
          },
        });
        showFeedback(`Deposited ${data.item?.name || 'item'} into bank`);
      } else {
        showFeedback(data.detail || 'Failed to deposit', true);
      }
    } catch (err) {
      showFeedback('Connection error', true);
      console.error('[HeroDetailPanel] Bank deposit error:', err);
    } finally {
      setLoading(false);
    }
  }, [loading, gameState.username, hero.hero_id, dispatch]);

  // ---------- Select for Dungeon ----------
  const handleSelectForDungeon = () => {
    dispatch({ type: 'SELECT_HERO', payload: hero.hero_id });
    if (onSelectHero) onSelectHero(hero.hero_id);
  };

  // ---------- Dismiss Hero ----------
  const [confirmDismiss, setConfirmDismiss] = useState(false);

  const handleDismissHero = useCallback(async () => {
    if (loading) return;
    setLoading(true);
    try {
      const res = await apiFetch('/api/town/dismiss', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          username: gameState.username,
          hero_id: hero.hero_id,
        }),
      });
      const data = await res.json();
      if (res.ok) {
        dispatch({
          type: 'DISMISS_HERO',
          payload: {
            hero_id: hero.hero_id,
            heroes: data.heroes,
          },
        });
        onClose(); // Close the panel after dismissal
      } else {
        showFeedback(data.detail || 'Failed to dismiss hero', true);
      }
    } catch (err) {
      showFeedback('Connection error', true);
      console.error('[HeroDetailPanel] Dismiss error:', err);
    } finally {
      setLoading(false);
      setConfirmDismiss(false);
    }
  }, [loading, gameState.username, hero.hero_id, dispatch, onClose]);

  const slots = ['weapon', 'armor', 'accessory'];

  return (
    <div className="hero-detail-overlay" onClick={onClose}>
      <div className="hero-detail-panel" onClick={e => e.stopPropagation()}>
        {/* Header */}
        <div className="detail-header">
          <div className="detail-header-left">
            <HeroSprite
              classId={hero.class_id}
              variant={hero.sprite_variant || 1}
              size={96}
              className="detail-hero-sprite"
            />
            <div>
              <h3 className="detail-hero-name">{hero.name}</h3>
              <span className="detail-hero-class" style={{ color: classDef.color || '#aaa' }}>
                {classDef.name || hero.class_id}
              </span>
            </div>
          </div>
          <div className="detail-header-right">
            {hero.matches_survived > 0 && (
              <span className="detail-track">{hero.matches_survived} runs</span>
            )}
            {hero.enemies_killed > 0 && (
              <span className="detail-track">{hero.enemies_killed} kills</span>
            )}
            <button className="detail-close-btn" onClick={onClose} title="Close">✕</button>
          </div>
        </div>

        {/* Feedback message */}
        {actionFeedback && (
          <div className={`detail-feedback ${actionFeedback.isError ? 'feedback-error' : 'feedback-success'}`}>
            {actionFeedback.msg}
          </div>
        )}

        <div className="detail-body">
          {/* Left column: Stats + Equipment */}
          <div className="detail-left-col">
            {/* Stats with bonus breakdown */}
            <div className="detail-stats-section">
              <h4 className="detail-section-title">Stats</h4>
              <div className="detail-stats-grid">
                <div className="detail-stat">
                  <span className="detail-stat-label">HP</span>
                  <span className="detail-stat-value">
                    {hero.stats.max_hp}
                    {bonuses.max_hp > 0 && (
                      <span className="stat-bonus">+{bonuses.max_hp}</span>
                    )}
                  </span>
                </div>
                <div className="detail-stat">
                  <span className="detail-stat-label">Melee</span>
                  <span className="detail-stat-value">
                    {hero.stats.attack_damage}
                    {bonuses.attack_damage > 0 && (
                      <span className="stat-bonus">+{bonuses.attack_damage}</span>
                    )}
                  </span>
                </div>
                <div className="detail-stat">
                  <span className="detail-stat-label">Ranged</span>
                  <span className="detail-stat-value">
                    {hero.stats.ranged_damage}
                    {bonuses.ranged_damage > 0 && (
                      <span className="stat-bonus">+{bonuses.ranged_damage}</span>
                    )}
                  </span>
                </div>
                <div className="detail-stat">
                  <span className="detail-stat-label">Armor</span>
                  <span className="detail-stat-value">
                    {hero.stats.armor}
                    {bonuses.armor > 0 && (
                      <span className="stat-bonus">+{bonuses.armor}</span>
                    )}
                  </span>
                </div>
                <div className="detail-stat">
                  <span className="detail-stat-label">Vision</span>
                  <span className="detail-stat-value">{hero.stats.vision_range}</span>
                </div>
              </div>
            </div>

            {/* Equipment Slots */}
            <div className="detail-equipment-section">
              <h4 className="detail-section-title">Equipment</h4>
              <div className="detail-equip-slots">
                {slots.map((slot) => {
                  const item = equipment[slot] || null;
                  const rarity = item?.rarity || 'common';
                  return (
                    <div
                      key={slot}
                      className={`detail-equip-slot ${item ? `has-item rarity-border-${rarity}` : ''}`}
                      onClick={() => item && !loading && handleUnequip(slot)}
                      onMouseEnter={() => item && setHoveredItem({ item, source: 'equip', slot })}
                      onMouseLeave={() => setHoveredItem(null)}
                    >
                      <span className="detail-slot-icon">{SLOT_ICONS[slot]}</span>
                      <div className="detail-slot-info">
                        <span className="detail-slot-label">{SLOT_LABELS[slot]}</span>
                        {item ? (
                          <span className={`detail-slot-item rarity-${rarity}`}>{item.name}</span>
                        ) : (
                          <span className="detail-slot-empty">Empty</span>
                        )}
                      </div>
                      {item && <span className="detail-slot-action">✕</span>}
                    </div>
                  );
                })}
              </div>
            </div>

            {/* Dungeon select */}
            <button
              className={`btn-detail-select ${isSelected ? 'btn-selected' : ''} ${!canSelect ? 'btn-disabled' : ''}`}
              onClick={canSelect ? handleSelectForDungeon : undefined}
              disabled={!canSelect}
            >
              {isSelected ? `Selected (#${selectionIndex + 1})` : (gameState.selectedHeroIds || []).length >= 4 ? 'Party Full (4/4)' : 'Select for Dungeon'}
            </button>

            {/* Dismiss hero */}
            {!confirmDismiss ? (
              <button
                className="btn-dismiss-hero"
                onClick={() => setConfirmDismiss(true)}
                disabled={loading}
              >
                Dismiss Hero
              </button>
            ) : (
              <div className="dismiss-confirm">
                <span className="dismiss-warning">Remove {hero.name} permanently? All gear will be lost.</span>
                <div className="dismiss-confirm-actions">
                  <button
                    className="btn-dismiss-yes"
                    onClick={handleDismissHero}
                    disabled={loading}
                  >
                    {loading ? '...' : 'Confirm'}
                  </button>
                  <button
                    className="btn-dismiss-no"
                    onClick={() => setConfirmDismiss(false)}
                  >
                    Cancel
                  </button>
                </div>
              </div>
            )}
          </div>

          {/* Right column: Bag */}
          <div className="detail-right-col">
            <div className="detail-bag-section">
              <div className="detail-bag-header">
                <h4 className="detail-section-title">Bag</h4>
                <span className="detail-bag-count">{inventory.length}/10</span>
              </div>
              <div className="detail-bag-grid">
                {Array.from({ length: 10 }, (_, i) => {
                  const item = inventory[i] || null;
                  const rarity = item?.rarity || 'common';
                  const isEquippable = item?.item_type && item.item_type !== 'consumable';

                  return (
                    <div
                      key={i}
                      className={`detail-bag-slot ${item ? `has-item rarity-border-${rarity}` : ''}`}
                      onMouseEnter={() => item && setHoveredItem({ item, source: 'bag', index: i })}
                      onMouseLeave={() => setHoveredItem(null)}
                    >
                      {item ? (
                        <>
                          <div className="detail-bag-item-info">
                            <span className="detail-bag-icon">{ITEM_ICONS[item.item_type] || '?'}</span>
                            <span className={`detail-bag-name rarity-${rarity}`}>{item.name}</span>
                          </div>
                          <div className="detail-bag-actions">
                            {isEquippable && (
                              <button
                                className="btn-bag-action btn-bag-equip"
                                onClick={() => handleEquip(i)}
                                disabled={loading}
                                title="Equip"
                              >
                                Equip
                              </button>
                            )}
                            <button
                              className="btn-bag-action btn-bag-bank"
                              onClick={() => handleBankDeposit(i)}
                              disabled={loading || bankFull}
                              title={bankFull ? 'Bank is full (20/20)' : 'Deposit to bank vault'}
                            >
                              Bank
                            </button>
                            {otherHeroes.length > 0 && (
                              <button
                                className="btn-bag-action btn-bag-transfer"
                                onClick={() => setTransferItem({ index: i, item })}
                                disabled={loading}
                                title="Transfer to another hero"
                              >
                                Transfer
                              </button>
                            )}
                          </div>
                        </>
                      ) : (
                        <span className="detail-bag-empty">•</span>
                      )}
                    </div>
                  );
                })}
              </div>
            </div>
          </div>
        </div>

        {/* Item Tooltip */}
        {hoveredItem?.item && (
          <div className="detail-tooltip-container">
            <ItemTooltip
              item={hoveredItem.item}
              hint={
                hoveredItem.source === 'equip'
                  ? 'Click to unequip'
                  : hoveredItem.item.item_type !== 'consumable'
                  ? 'Click Equip to wear • Click Transfer to send to another hero'
                  : otherHeroes.length > 0
                  ? 'Click Transfer to send to another hero'
                  : null
              }
            />
          </div>
        )}

        {/* Transfer Modal */}
        {transferItem && (
          <div className="transfer-modal-overlay" onClick={() => setTransferItem(null)}>
            <div className="transfer-modal" onClick={e => e.stopPropagation()}>
              <h4 className="transfer-title">
                Transfer {transferItem.item.name}
              </h4>
              <p className="transfer-subtitle">
                From <strong>{hero.name}</strong> — choose a destination hero:
              </p>
              <div className="transfer-hero-list">
                {otherHeroes.map((h) => {
                  const hClass = availableClasses?.[h.class_id] || {};
                  const hInvCount = (h.inventory || []).length;
                  const isFull = hInvCount >= 10;
                  return (
                    <button
                      key={h.hero_id}
                      className={`transfer-hero-btn ${isFull ? 'transfer-hero-full' : ''}`}
                      onClick={() => !isFull && handleTransfer(h.hero_id)}
                      disabled={isFull || loading}
                    >
                      <HeroSprite
                        classId={h.class_id}
                        variant={h.sprite_variant || 1}
                        size={36}
                        className="transfer-hero-sprite"
                      />
                      <div className="transfer-hero-info">
                        <span className="transfer-hero-name">{h.name}</span>
                        <span className="transfer-hero-class" style={{ color: hClass.color || '#aaa' }}>
                          {hClass.name || h.class_id}
                        </span>
                      </div>
                      <span className={`transfer-hero-bag ${isFull ? 'bag-full' : ''}`}>
                        {hInvCount}/10
                      </span>
                    </button>
                  );
                })}
              </div>
              <button className="transfer-cancel-btn" onClick={() => setTransferItem(null)}>
                Cancel
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
