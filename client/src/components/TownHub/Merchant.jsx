import React, { useState, useEffect, useCallback } from 'react';
import { useGameState, useGameDispatch } from '../../context/GameStateContext';
import HeroSprite from './HeroSprite';

/**
 * Merchant — buy/sell items in the Town Hub.
 *
 * Left panel: Merchant stock (items to buy)
 * Right panel: Selected hero's inventory (items to sell)
 *
 * Phase 5 Feature 6: Merchant buy/sell system.
 */

const RARITY_COLORS = {
  common: '#9d9d9d', uncommon: '#9d9d9d',
  magic: '#4488ff', rare: '#ffcc00', epic: '#b040ff',
  unique: '#ff8800', set: '#00cc44',
};
const CATEGORY_LABELS = {
  consumables: 'Consumables',
  weapons: 'Weapons',
  armor: 'Armor',
  accessories: 'Accessories',
};
const CATEGORY_ORDER = ['consumables', 'weapons', 'armor', 'accessories'];

export default function Merchant({ availableClasses }) {
  const gameState = useGameState();
  const dispatch = useGameDispatch();

  const [stock, setStock] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [selectedHeroId, setSelectedHeroId] = useState(null);
  const [confirmAction, setConfirmAction] = useState(null); // { type: 'buy'|'sell', ... }
  const [transactionMsg, setTransactionMsg] = useState(null);

  const gold = gameState.gold;
  const heroes = (gameState.heroes || []).filter(h => h.is_alive);
  const selectedHero = heroes.find(h => h.hero_id === selectedHeroId);

  // Auto-select first hero if none selected
  useEffect(() => {
    if (!selectedHeroId && heroes.length > 0) {
      setSelectedHeroId(heroes[0].hero_id);
    }
  }, [heroes, selectedHeroId]);

  // Fetch merchant stock on mount
  const fetchStock = useCallback(async () => {
    setLoading(true);
    try {
      const res = await fetch('/api/town/merchant/stock');
      if (res.ok) {
        const data = await res.json();
        setStock(data.stock || []);
      } else {
        setError('Failed to load merchant stock');
      }
    } catch (err) {
      setError('Failed to connect to merchant');
      console.error('[Merchant] Fetch error:', err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchStock();
  }, [fetchStock]);

  // Clear transaction message after 3 seconds
  useEffect(() => {
    if (transactionMsg) {
      const timer = setTimeout(() => setTransactionMsg(null), 3000);
      return () => clearTimeout(timer);
    }
  }, [transactionMsg]);

  const handleBuy = async (item) => {
    if (!selectedHeroId) {
      setError('Select a hero first');
      return;
    }
    setConfirmAction({
      type: 'buy',
      item,
      price: item.buy_price,
      heroName: selectedHero?.name || 'hero',
    });
  };

  const handleSell = async (itemIndex, item) => {
    if (!selectedHeroId) return;
    setConfirmAction({
      type: 'sell',
      item,
      itemIndex,
      price: item.sell_value || 1,
      heroName: selectedHero?.name || 'hero',
    });
  };

  const confirmTransaction = async () => {
    if (!confirmAction) return;
    setError(null);

    try {
      if (confirmAction.type === 'buy') {
        const res = await fetch('/api/town/merchant/buy', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            username: gameState.username,
            hero_id: selectedHeroId,
            item_id: confirmAction.item.item_id,
          }),
        });
        const data = await res.json();
        if (res.ok) {
          dispatch({
            type: 'MERCHANT_BUY',
            payload: {
              gold: data.gold,
              hero_id: data.hero_id,
              item: data.item,
            },
          });
          setTransactionMsg(`Bought ${data.item.name} for ${confirmAction.price}g`);
        } else {
          setError(data.detail || 'Purchase failed');
        }
      } else if (confirmAction.type === 'sell') {
        const res = await fetch('/api/town/merchant/sell', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            username: gameState.username,
            hero_id: selectedHeroId,
            item_index: confirmAction.itemIndex,
          }),
        });
        const data = await res.json();
        if (res.ok) {
          dispatch({
            type: 'MERCHANT_SELL',
            payload: {
              gold: data.gold,
              hero_id: data.hero_id,
              item_index: confirmAction.itemIndex,
            },
          });
          setTransactionMsg(`Sold ${data.sold_item?.name || 'item'} for ${data.sell_price}g`);
        } else {
          setError(data.detail || 'Sale failed');
        }
      }
    } catch (err) {
      setError('Transaction failed — network error');
      console.error('[Merchant] Transaction error:', err);
    } finally {
      setConfirmAction(null);
    }
  };

  const cancelConfirm = () => setConfirmAction(null);

  // Group stock by category
  const stockByCategory = {};
  for (const item of stock) {
    const cat = item.category || 'misc';
    if (!stockByCategory[cat]) stockByCategory[cat] = [];
    stockByCategory[cat].push(item);
  }

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

  if (loading) {
    return (
      <div className="merchant-panel">
        <p className="town-loading">The merchant unpacks their wares...</p>
      </div>
    );
  }

  return (
    <div className="merchant-panel">
      <div className="merchant-header">
        <h3>Merchant</h3>
        <span className="merchant-gold">{gold}g</span>
      </div>

      {error && <p className="merchant-error">{error}</p>}
      {transactionMsg && <p className="merchant-success">{transactionMsg}</p>}

      {/* Hero selector for transactions */}
      {heroes.length === 0 ? (
        <p className="town-placeholder">No living heroes. Visit the Hiring Hall first!</p>
      ) : (
        <>
          <div className="merchant-hero-select">
            <label className="merchant-label">Hero:</label>
            <div className="merchant-hero-tabs">
              {heroes.map(h => {
                const classDef = availableClasses?.[h.class_id] || {};
                return (
                  <button
                    key={h.hero_id}
                    className={`merchant-hero-btn ${selectedHeroId === h.hero_id ? 'merchant-hero-active' : ''}`}
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
                    <span className="merchant-hero-inv">{(h.inventory || []).length}/10</span>
                  </button>
                );
              })}
            </div>
          </div>

          <div className="merchant-columns">
            {/* LEFT: Buy panel */}
            <div className="merchant-buy-panel">
              <h4 className="merchant-section-title">Buy</h4>
              {CATEGORY_ORDER.map(cat => {
                const items = stockByCategory[cat];
                if (!items || items.length === 0) return null;
                return (
                  <div key={cat} className="merchant-category">
                    <div className="merchant-category-label">{CATEGORY_LABELS[cat] || cat}</div>
                    {items.map(item => {
                      const canAfford = gold >= item.buy_price;
                      const canBuy = canAfford && !heroInvFull && selectedHero;
                      return (
                        <div
                          key={item.item_id}
                          className={`merchant-item ${!canBuy ? 'merchant-item-disabled' : ''}`}
                        >
                          <div className="merchant-item-info">
                            <span
                              className="merchant-item-name"
                              style={{ color: RARITY_COLORS[item.rarity] || '#999' }}
                            >
                              {item.name}
                            </span>
                            <span className="merchant-item-stats">{getStatSummary(item)}</span>
                            {item.description && (
                              <span className="merchant-item-desc">{item.description}</span>
                            )}
                          </div>
                          <div className="merchant-item-action">
                            <span className="merchant-price merchant-price-buy">
                              {item.buy_price}g
                            </span>
                            <button
                              className="btn-merchant-buy"
                              onClick={() => handleBuy(item)}
                              disabled={!canBuy}
                              title={
                                !selectedHero ? 'Select a hero' :
                                heroInvFull ? 'Inventory full' :
                                !canAfford ? `Need ${item.buy_price}g` : `Buy for ${item.buy_price}g`
                              }
                            >
                              Buy
                            </button>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                );
              })}
            </div>

            {/* RIGHT: Sell panel */}
            <div className="merchant-sell-panel">
              <h4 className="merchant-section-title">
                Sell
                {selectedHero && (
                  <span className="merchant-inv-count">
                    {' '}({heroInvCount}/10)
                  </span>
                )}
              </h4>
              {!selectedHero ? (
                <p className="merchant-empty">Select a hero to sell items</p>
              ) : heroInvCount === 0 ? (
                <p className="merchant-empty">No items in inventory</p>
              ) : (
                <div className="merchant-sell-list">
                  {(selectedHero.inventory || []).map((item, idx) => (
                    <div key={idx} className="merchant-item">
                      <div className="merchant-item-info">
                        <span
                          className="merchant-item-name"
                          style={{ color: RARITY_COLORS[item.rarity] || '#999' }}
                        >
                          {item.name}
                        </span>
                        <span className="merchant-item-stats">{getStatSummary(item)}</span>
                      </div>
                      <div className="merchant-item-action">
                        <span className="merchant-price merchant-price-sell">
                          {item.sell_value || 1}g
                        </span>
                        <button
                          className="btn-merchant-sell"
                          onClick={() => handleSell(idx, item)}
                        >
                          Sell
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        </>
      )}

      {/* Confirmation modal */}
      {confirmAction && (
        <div className="merchant-confirm-overlay">
          <div className="merchant-confirm-modal">
            <h4>
              {confirmAction.type === 'buy' ? 'Confirm Purchase' : 'Confirm Sale'}
            </h4>
            <p className="merchant-confirm-text">
              {confirmAction.type === 'buy'
                ? `Buy ${confirmAction.item.name} for ${confirmAction.price}g?`
                : `Sell ${confirmAction.item.name} for ${confirmAction.price}g?`}
            </p>
            <p className="merchant-confirm-hero">
              Hero: <strong>{confirmAction.heroName}</strong>
            </p>
            <div className="merchant-confirm-actions">
              <button className="btn-confirm-yes" onClick={confirmTransaction}>
                {confirmAction.type === 'buy' ? 'Buy' : 'Sell'}
              </button>
              <button className="btn-confirm-no" onClick={cancelConfirm}>
                Cancel
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
