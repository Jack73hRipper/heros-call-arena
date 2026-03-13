import React, { useState, useEffect } from 'react';
import { useGameState, useGameDispatch } from '../../context/GameStateContext';
import { apiFetch } from '../../utils/serverUrl';
import HeroSprite from './HeroSprite';
import { formatStatBonuses } from '../../utils/itemUtils';

/**
 * Bank — account-wide shared stash for item storage.
 *
 * Left panel: Selected hero's inventory (deposit into vault)
 * Right panel: Bank vault (up to 20 slots)
 *
 * Items in the bank persist across hero deaths, making it a strategic
 * tool to protect valuable gear before risky dungeon runs.
 *
 * Phase 5 Feature 8: Shared Bank / Stash system.
 */

const RARITY_COLORS = {
  common: '#9d9d9d', uncommon: '#9d9d9d',
  magic: '#4488ff', rare: '#ffcc00', epic: '#b040ff',
  unique: '#ff8800', set: '#00cc44',
};
const BANK_CAPACITY = 20;

function BankItemTooltip({ item, x, y }) {
  if (!item) return null;
  const rarity = item.rarity || 'common';
  const stats = formatStatBonuses(item.stat_bonuses);
  return (
    <div
      className="bank-tooltip-wrapper"
      style={{
        position: 'fixed',
        left: x,
        top: y,
        transform: 'translate(-50%, -100%) translateY(-8px)',
        zIndex: 9999,
        pointerEvents: 'none',
      }}
    >
      <div className={`gear-tooltip rarity-border-${rarity}`}>
        <div className={`gear-tooltip-name rarity-${rarity}`}>{item.name}</div>
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
      </div>
    </div>
  );
}

export default function Bank({ availableClasses }) {
  const gameState = useGameState();
  const dispatch = useGameDispatch();

  const [selectedHeroId, setSelectedHeroId] = useState(null);
  const [error, setError] = useState(null);
  const [feedback, setFeedback] = useState(null);
  const [loading, setLoading] = useState(false);
  const [hoveredItem, setHoveredItem] = useState(null); // { item, x, y }

  const bank = gameState.bank || [];
  const heroes = (gameState.heroes || []).filter(h => h.is_alive);
  const selectedHero = heroes.find(h => h.hero_id === selectedHeroId);

  // Auto-select first hero if none selected
  useEffect(() => {
    if (!selectedHeroId && heroes.length > 0) {
      setSelectedHeroId(heroes[0].hero_id);
    }
  }, [heroes, selectedHeroId]);

  // Clear feedback after 3 seconds
  useEffect(() => {
    if (feedback) {
      const timer = setTimeout(() => setFeedback(null), 3000);
      return () => clearTimeout(timer);
    }
  }, [feedback]);

  // Clear error after 5 seconds
  useEffect(() => {
    if (error) {
      const timer = setTimeout(() => setError(null), 5000);
      return () => clearTimeout(timer);
    }
  }, [error]);

  const handleDeposit = async (itemIndex) => {
    if (!selectedHeroId || loading) return;
    setError(null);
    setLoading(true);

    try {
      const res = await apiFetch('/api/town/bank/deposit', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          username: gameState.username,
          hero_id: selectedHeroId,
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
        setFeedback(`Deposited ${data.item?.name || 'item'} into bank`);
      } else {
        setError(data.detail || 'Deposit failed');
      }
    } catch (err) {
      setError('Deposit failed — network error');
      console.error('[Bank] Deposit error:', err);
    } finally {
      setLoading(false);
    }
  };

  const handleWithdraw = async (bankIndex) => {
    if (!selectedHeroId || loading) return;
    setError(null);
    setLoading(true);

    try {
      const res = await apiFetch('/api/town/bank/withdraw', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          username: gameState.username,
          hero_id: selectedHeroId,
          bank_index: bankIndex,
        }),
      });
      const data = await res.json();
      if (res.ok) {
        dispatch({
          type: 'BANK_WITHDRAW',
          payload: {
            hero_id: data.hero_id,
            inventory: data.inventory,
            bank: data.bank,
          },
        });
        setFeedback(`Withdrew ${data.item?.name || 'item'} to ${selectedHero?.name || 'hero'}`);
      } else {
        setError(data.detail || 'Withdraw failed');
      }
    } catch (err) {
      setError('Withdraw failed — network error');
      console.error('[Bank] Withdraw error:', err);
    } finally {
      setLoading(false);
    }
  };

  const getStatSummary = (item) => {
    const parts = [];
    const b = item.stat_bonuses || {};
    if (b.attack_damage) parts.push(`+${b.attack_damage} Atk`);
    if (b.ranged_damage) parts.push(`+${b.ranged_damage} Rng`);
    if (b.armor) parts.push(`+${b.armor} Arm`);
    if (b.max_hp) parts.push(`+${b.max_hp} HP`);
    if (item.consumable_effect) {
      if (item.consumable_effect.type === 'heal') {
        parts.push(`Heal ${item.consumable_effect.magnitude} HP`);
      } else if (item.consumable_effect.type === 'portal') {
        parts.push('Party escape');
      }
    }
    return parts.join(', ');
  };

  const heroInvCount = selectedHero?.inventory?.length || 0;
  const heroInvFull = heroInvCount >= 10;
  const bankFull = bank.length >= BANK_CAPACITY;

  return (
    <div className="bank-panel">
      <div className="bank-header">
        <h3>Bank Vault</h3>
        <span className="bank-capacity">{bank.length}/{BANK_CAPACITY} slots</span>
      </div>

      {error && <p className="bank-error">{error}</p>}
      {feedback && <p className="bank-success">{feedback}</p>}

      {heroes.length === 0 ? (
        <p className="town-placeholder">No living heroes. Visit the Hiring Hall first!</p>
      ) : (
        <>
          {/* Hero selector */}
          <div className="bank-hero-select">
            <label className="bank-label">Hero:</label>
            <div className="bank-hero-tabs">
              {heroes.map(h => {
                const classDef = availableClasses?.[h.class_id] || {};
                return (
                  <button
                    key={h.hero_id}
                    className={`bank-hero-btn ${selectedHeroId === h.hero_id ? 'bank-hero-active' : ''}`}
                    onClick={() => setSelectedHeroId(h.hero_id)}
                    style={{
                      borderColor: selectedHeroId === h.hero_id ? (classDef.color || '#e0a040') : undefined,
                    }}
                  >
                    <HeroSprite
                      classId={h.class_id}
                      variant={h.sprite_variant || 1}
                      size={32}
                    />{' '}
                    {h.name}
                    <span className="bank-hero-inv">{(h.inventory || []).length}/10</span>
                  </button>
                );
              })}
            </div>
          </div>

          <div className="bank-info-banner">
            <span className="bank-info-text">
              Items stored here survive hero death. Bank valuable gear before risky dungeon runs!
            </span>
          </div>

          <div className="bank-columns">
            {/* LEFT: Hero inventory (deposit into vault) */}
            <div className="bank-hero-panel">
              <h4 className="bank-section-title bank-title-hero">
                <span className="bank-panel-icon">🎒</span>
                {selectedHero ? selectedHero.name : 'Hero'}'s Bag
                {selectedHero && (
                  <span className="bank-slot-count">
                    {' '}({heroInvCount}/10)
                  </span>
                )}
              </h4>
              {!selectedHero ? (
                <p className="bank-empty">Select a hero to manage items</p>
              ) : heroInvCount === 0 ? (
                <p className="bank-empty">No items in inventory</p>
              ) : (
                <div className="bank-item-list">
                  {(selectedHero.inventory || []).map((item, idx) => {
                    const canDeposit = !bankFull && !loading;
                    return (
                      <div
                        key={idx}
                        className={`bank-item ${!canDeposit ? 'bank-item-disabled' : ''}`}
                        onMouseEnter={(e) => {
                          const rect = e.currentTarget.getBoundingClientRect();
                          setHoveredItem({ item, x: rect.left + rect.width / 2, y: rect.top });
                        }}
                        onMouseLeave={() => setHoveredItem(null)}
                      >
                        <div className="bank-item-info">
                          <span
                            className="bank-item-name"
                            style={{ color: RARITY_COLORS[item.rarity] || '#999' }}
                          >
                            {item.name || item.item_id}
                          </span>
                          <span className="bank-item-stats">{getStatSummary(item)}</span>
                        </div>
                        <div className="bank-item-action">
                          <button
                            className="btn-bank-deposit"
                            onClick={() => handleDeposit(idx)}
                            disabled={!canDeposit}
                            title={
                              bankFull ? 'Bank is full' :
                              loading ? 'Processing...' :
                              'Deposit to bank'
                            }
                          >
                            Deposit →
                          </button>
                        </div>
                      </div>
                    );
                  })}
                </div>
              )}
            </div>

            {/* RIGHT: Bank vault */}
            <div className="bank-vault-panel">
              <h4 className="bank-section-title bank-title-vault">
                <span className="bank-panel-icon">🏦</span>
                Vault
                <span className="bank-slot-count"> ({bank.length}/{BANK_CAPACITY})</span>
              </h4>
              {bank.length === 0 ? (
                <p className="bank-empty">The vault is empty. Deposit items from a hero's bag.</p>
              ) : (
                <div className="bank-item-list">
                  {bank.map((item, idx) => {
                    const canWithdraw = selectedHero && !heroInvFull && !loading;
                    return (
                      <div
                        key={idx}
                        className={`bank-item ${!canWithdraw ? 'bank-item-disabled' : ''}`}
                        onMouseEnter={(e) => {
                          const rect = e.currentTarget.getBoundingClientRect();
                          setHoveredItem({ item, x: rect.left + rect.width / 2, y: rect.top });
                        }}
                        onMouseLeave={() => setHoveredItem(null)}
                      >
                        <div className="bank-item-info">
                          <span
                            className="bank-item-name"
                            style={{ color: RARITY_COLORS[item.rarity] || '#999' }}
                          >
                            {item.name || item.item_id}
                          </span>
                          <span className="bank-item-stats">{getStatSummary(item)}</span>
                          {item.description && (
                            <span className="bank-item-desc">{item.description}</span>
                          )}
                        </div>
                        <div className="bank-item-action">
                          <button
                            className="btn-bank-withdraw"
                            onClick={() => handleWithdraw(idx)}
                            disabled={!canWithdraw}
                            title={
                              !selectedHero ? 'Select a hero' :
                              heroInvFull ? 'Hero inventory full' :
                              loading ? 'Processing...' :
                              `Withdraw to ${selectedHero.name}`
                            }
                          >
                            ← Withdraw
                          </button>
                        </div>
                      </div>
                    );
                  })}
                </div>
              )}
            </div>
          </div>
        </>
      )}

      {/* Item Tooltip */}
      {hoveredItem && (
        <BankItemTooltip item={hoveredItem.item} x={hoveredItem.x} y={hoveredItem.y} />
      )}
    </div>
  );
}
