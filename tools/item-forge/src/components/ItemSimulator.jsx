// ─────────────────────────────────────────────────────────
// ItemSimulator.jsx — Random item generator, stat analysis
// & drop-rate calculator
// ─────────────────────────────────────────────────────────

import React, { useState, useMemo, useCallback } from 'react';

// ── helpers ──────────────────────────────────────────────
function pick(arr) { return arr[Math.floor(Math.random() * arr.length)]; }
function randBetween(min, max) { return min + Math.random() * (max - min); }
function randInt(min, max) { return Math.floor(randBetween(min, max + 1)); }
function clamp(v, lo, hi) { return Math.max(lo, Math.min(hi, v)); }

function fmtStat(stat, val, meta) {
  const info = meta?.stats?.[stat];
  if (!info) return `${stat}: ${val}`;
  if (info.type === 'float') return `+${(val * 100).toFixed(1)}% ${info.label}`;
  return `${val > 0 ? '+' : ''}${Math.round(val)} ${info.label}`;
}

function calcBudget(stats, meta) {
  let total = 0;
  for (const [stat, val] of Object.entries(stats)) {
    const info = meta?.stats?.[stat];
    if (!info) continue;
    total += Math.abs(val) * info.budget_pts;
  }
  return Math.round(total * 10) / 10;
}

function budgetColor(budget, rarity, meta) {
  const range = meta?.stat_budget_ranges?.[rarity];
  if (!range) return 'var(--text)';
  if (budget < range.min) return 'var(--warning)';
  if (budget > range.max) return 'var(--danger)';
  return 'var(--success)';
}

// ── weighted random selection ────────────────────────────
function weightedPick(items) {
  const total = items.reduce((sum, i) => sum + (i._weight || 0), 0);
  let roll = Math.random() * total;
  for (const item of items) {
    roll -= item._weight || 0;
    if (roll <= 0) return item;
  }
  return items[items.length - 1];
}

// ── roll a single affix value at a given ilvl ────────────
function rollAffixValue(affix, ilvl) {
  const scaled = affix.min_value + (affix.ilvl_scaling || 0) * ilvl;
  const max = affix.max_value;
  const effectiveMin = Math.min(scaled, max);
  const v = randBetween(affix.min_value, clamp(effectiveMin, affix.min_value, max));
  const info_type = typeof affix.min_value === 'number' && affix.min_value % 1 !== 0 ? 'float' : 'int';
  return info_type === 'float' ? Math.round(v * 1000) / 1000 : Math.round(v);
}

// ── generate a random item ──────────────────────────────
function generateItem(baseItems, affixes, rarity, slot, ilvl, affixCounts, itemNames) {
  // 1. Pick a base item that matches the slot
  const candidates = Object.values(baseItems.items || baseItems).filter(i => {
    if (slot !== 'any' && i.equip_slot !== slot) return false;
    return true;
  });
  if (!candidates.length) return null;
  const base = pick(candidates);

  // 2. Collect base stats
  const stats = {};
  for (const [k, v] of Object.entries(base.stat_bonuses || {})) {
    if (v !== 0) stats[k] = v;
  }

  // 3. Roll affixes based on rarity
  const counts = affixCounts[rarity] || { min: 0, max: 0 };
  const numAffixes = randInt(counts.min, counts.max);

  // Split into prefix + suffix budget
  const prefixBudget = Math.ceil(numAffixes / 2);
  const suffixBudget = numAffixes - prefixBudget;

  const rolledAffixes = [];

  // Roll prefixes
  const validPrefixes = Object.values(affixes.prefixes || {})
    .filter(a => a.allowed_slots?.includes(base.equip_slot))
    .map(a => ({ ...a, _weight: a.weight || 1 }));

  const usedPrefixStats = new Set();
  for (let i = 0; i < prefixBudget && validPrefixes.length > 0; i++) {
    const available = validPrefixes.filter(a => !usedPrefixStats.has(a.stat));
    if (!available.length) break;
    const chosen = weightedPick(available);
    const val = rollAffixValue(chosen, ilvl);
    rolledAffixes.push({ ...chosen, rolled_value: val, type: 'prefix' });
    usedPrefixStats.add(chosen.stat);
    stats[chosen.stat] = (stats[chosen.stat] || 0) + val;
  }

  // Roll suffixes
  const validSuffixes = Object.values(affixes.suffixes || {})
    .filter(a => a.allowed_slots?.includes(base.equip_slot))
    .map(a => ({ ...a, _weight: a.weight || 1 }));

  const usedSuffixStats = new Set();
  for (let i = 0; i < suffixBudget && validSuffixes.length > 0; i++) {
    const available = validSuffixes.filter(a => !usedSuffixStats.has(a.stat));
    if (!available.length) break;
    const chosen = weightedPick(available);
    const val = rollAffixValue(chosen, ilvl);
    rolledAffixes.push({ ...chosen, rolled_value: val, type: 'suffix' });
    usedSuffixStats.add(chosen.stat);
    stats[chosen.stat] = (stats[chosen.stat] || 0) + val;
  }

  // Build display name (mirrors server naming tiers)
  const baseName = base.name || base.item_id;
  let name;
  if (rarity === 'common' || rarity === 'uncommon') {
    name = baseName;
  } else if (rarity === 'magic') {
    // Magic: first prefix + base + first suffix (max 1 each)
    const pre = rolledAffixes.find(a => a.type === 'prefix');
    const suf = rolledAffixes.find(a => a.type === 'suffix');
    name = [pre?.name, baseName, suf?.name].filter(Boolean).join(' ');
  } else if (rarity === 'rare') {
    // Rare: pick the rarest (lowest weight) prefix & suffix for the name
    const prefixes = rolledAffixes.filter(a => a.type === 'prefix');
    const suffixes = rolledAffixes.filter(a => a.type === 'suffix');
    const bestPre = prefixes.length
      ? prefixes.reduce((best, a) => (a.weight || 100) < (best.weight || 100) ? a : best)
      : null;
    const bestSuf = suffixes.length
      ? suffixes.reduce((best, a) => (a.weight || 100) < (best.weight || 100) ? a : best)
      : null;
    name = [bestPre?.name, baseName, bestSuf?.name].filter(Boolean).join(' ');
  } else {
    // Epic: grimdark title from name pool
    const slotKey = base.equip_slot === 'weapon' ? 'weapon_names'
      : base.equip_slot === 'armor' ? 'armor_names'
      : base.equip_slot === 'accessory' ? 'accessory_names'
      : 'weapon_names';
    const pool = itemNames?.[slotKey];
    name = pool?.length ? pick(pool) : baseName;
  }

  return {
    name,
    base_name: base.name || base.item_id,
    base_id: base.item_id,
    rarity,
    equip_slot: base.equip_slot,
    ilvl,
    stats,
    affixes: rolledAffixes,
    base_stats: base.stat_bonuses || {},
  };
}

// ═════════════════════════════════════════════════════════
// Main Component
// ═════════════════════════════════════════════════════════
export default function ItemSimulator({ configs, statsMeta }) {
  const [tab, setTab] = useState('generator');

  return (
    <div>
      <div className="section-header" style={{ marginBottom: 0 }}>
        <h2>Item Simulator</h2>
      </div>
      <div className="filter-bar" style={{ marginBottom: 16 }}>
        {['generator', 'distribution', 'droprates'].map(t => (
          <button key={t} className={`btn btn-sm ${tab === t ? 'btn-primary' : ''}`}
            onClick={() => setTab(t)}
            style={{ textTransform: 'capitalize' }}>
            {t === 'generator' ? '🎲 Generator' : t === 'distribution' ? '📊 Distribution' : '💧 Drop Rates'}
          </button>
        ))}
      </div>

      {tab === 'generator' && <GeneratorTab configs={configs} statsMeta={statsMeta} />}
      {tab === 'distribution' && <DistributionTab configs={configs} statsMeta={statsMeta} />}
      {tab === 'droprates' && <DropRateTab configs={configs} statsMeta={statsMeta} />}
    </div>
  );
}

// ═════════════════════════════════════════════════════════
// Generator Tab — roll items + compare
// ═════════════════════════════════════════════════════════
function GeneratorTab({ configs, statsMeta }) {
  const [rarity, setRarity] = useState('rare');
  const [slot, setSlot] = useState('any');
  const [ilvl, setIlvl] = useState(5);
  const [items, setItems] = useState([]);
  const [pinned, setPinned] = useState(null);

  const affixCounts = statsMeta?.rarity_affix_counts || {};
  const rarityColors = statsMeta?.rarity_colors || {};

  function rollOne() {
    if (!configs.items || !configs.affixes) return;
    const item = generateItem(configs.items, configs.affixes, rarity, slot, ilvl, affixCounts, configs.item_names);
    if (item) setItems(prev => [item, ...prev].slice(0, 50));
  }

  function rollBatch(n) {
    if (!configs.items || !configs.affixes) return;
    const batch = [];
    for (let i = 0; i < n; i++) {
      const item = generateItem(configs.items, configs.affixes, rarity, slot, ilvl, affixCounts, configs.item_names);
      if (item) batch.push(item);
    }
    setItems(prev => [...batch, ...prev].slice(0, 200));
  }

  return (
    <div>
      {/* Controls */}
      <div className="filter-bar" style={{ flexWrap: 'wrap' }}>
        <div>
          <label style={{ fontSize: 11, color: 'var(--text-dim)' }}>Rarity</label>
          <select value={rarity} onChange={e => setRarity(e.target.value)}>
            {['common', 'magic', 'rare', 'epic'].map(r => (
              <option key={r} value={r}>{r}</option>
            ))}
          </select>
        </div>
        <div>
          <label style={{ fontSize: 11, color: 'var(--text-dim)' }}>Slot</label>
          <select value={slot} onChange={e => setSlot(e.target.value)}>
            <option value="any">Any</option>
            {(statsMeta?.equip_slots || []).map(s => (
              <option key={s} value={s}>{s}</option>
            ))}
          </select>
        </div>
        <div>
          <label style={{ fontSize: 11, color: 'var(--text-dim)' }}>Item Level</label>
          <input type="range" min={1} max={20} value={ilvl}
            onChange={e => setIlvl(parseInt(e.target.value))}
            style={{ width: 100 }} />
          <span style={{ fontFamily: 'var(--font-mono)', marginLeft: 4 }}>{ilvl}</span>
        </div>
        <div className="flex-row gap-sm" style={{ marginLeft: 'auto' }}>
          <button className="btn btn-primary" onClick={rollOne}>🎲 Roll 1</button>
          <button className="btn" onClick={() => rollBatch(10)}>Roll 10</button>
          <button className="btn" onClick={() => rollBatch(100)}>Roll 100</button>
          <button className="btn btn-danger" onClick={() => { setItems([]); setPinned(null); }}>Clear</button>
        </div>
      </div>

      {/* Layout: items list + pinned comparison */}
      <div style={{ display: 'grid', gridTemplateColumns: pinned ? '1fr 320px' : '1fr', gap: 12, marginTop: 12 }}>
        {/* Item list */}
        <div>
          {items.length === 0 && (
            <div className="empty-state">
              <p>Roll some items to see results here.</p>
            </div>
          )}
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))', gap: 8 }}>
            {items.map((item, i) => (
              <ItemCard key={i} item={item} statsMeta={statsMeta} rarityColors={rarityColors}
                compare={pinned} onPin={() => setPinned(item)} isPinned={pinned === item} />
            ))}
          </div>
        </div>

        {/* Pinned compare panel */}
        {pinned && (
          <div className="card" style={{ borderColor: rarityColors[pinned.rarity], position: 'sticky', top: 12, alignSelf: 'start' }}>
            <div className="flex-row" style={{ marginBottom: 8 }}>
              <h4 style={{ margin: 0, color: rarityColors[pinned.rarity], fontSize: 13 }}>📌 Pinned</h4>
              <button className="btn btn-sm ml-auto" onClick={() => setPinned(null)}>✕</button>
            </div>
            <ItemCard item={pinned} statsMeta={statsMeta} rarityColors={rarityColors}
              compare={null} onPin={() => { }} isPinned={true} compact />
          </div>
        )}
      </div>
    </div>
  );
}

function ItemCard({ item, statsMeta, rarityColors, compare, onPin, isPinned, compact }) {
  const budget = calcBudget(item.stats, statsMeta);
  const bc = budgetColor(budget, item.rarity, statsMeta);

  return (
    <div className="card" style={{
      borderLeft: `3px solid ${rarityColors[item.rarity] || '#666'}`,
      opacity: isPinned ? 1 : 0.95,
      cursor: 'pointer',
      position: 'relative',
    }} onClick={onPin}>
      {/* Header */}
      <div style={{ marginBottom: 6 }}>
        <div style={{ color: rarityColors[item.rarity], fontWeight: 600, fontSize: 13 }}>{item.name}</div>
        <div className="flex-row" style={{ fontSize: 11, color: 'var(--text-dim)' }}>
          <span className={`slot-badge ${item.equip_slot}`}>{item.equip_slot}</span>
          <span style={{ marginLeft: 4 }}>iLvl {item.ilvl}</span>
          <span style={{ marginLeft: 'auto', color: bc, fontFamily: 'var(--font-mono)' }}>
            budget: {budget}
          </span>
        </div>
      </div>

      {/* Stats */}
      <div style={{ fontSize: 12, fontFamily: 'var(--font-mono)' }}>
        {Object.entries(item.stats).map(([stat, val]) => {
          if (val === 0) return null;
          const cmp = compare?.stats?.[stat];
          const diff = cmp !== undefined ? val - cmp : null;
          return (
            <div key={stat} className="flex-row" style={{ color: 'var(--success)' }}>
              <span>{fmtStat(stat, val, statsMeta)}</span>
              {diff !== null && diff !== 0 && (
                <span style={{ marginLeft: 'auto', color: diff > 0 ? '#0f0' : '#f44', fontSize: 10 }}>
                  {diff > 0 ? '▲' : '▼'} {Math.abs(Math.round(diff * 100) / 100)}
                </span>
              )}
            </div>
          );
        })}
      </div>

      {/* Affixes */}
      {!compact && item.affixes.length > 0 && (
        <div style={{ marginTop: 6, paddingTop: 6, borderTop: '1px solid var(--border)', fontSize: 11 }}>
          {item.affixes.map((a, i) => (
            <span key={i} style={{
              display: 'inline-block',
              background: a.type === 'prefix' ? 'rgba(68,136,255,0.15)' : 'rgba(255,204,0,0.15)',
              color: a.type === 'prefix' ? '#4488ff' : '#ffcc00',
              padding: '1px 6px', borderRadius: 3, fontSize: 10, marginRight: 4, marginBottom: 2,
            }}>
              {a.name}
            </span>
          ))}
        </div>
      )}
    </div>
  );
}

// ═════════════════════════════════════════════════════════
// Distribution Tab — simulate N items, show affix freq
// ═════════════════════════════════════════════════════════
function DistributionTab({ configs, statsMeta }) {
  const [slot, setSlot] = useState('any');
  const [rarity, setRarity] = useState('rare');
  const [ilvl, setIlvl] = useState(5);
  const [sampleSize, setSampleSize] = useState(1000);
  const [results, setResults] = useState(null);

  const affixCounts = statsMeta?.rarity_affix_counts || {};

  function runSimulation() {
    if (!configs.items || !configs.affixes) return;
    const affixFreq = {};
    const statTotals = {};
    const budgets = [];
    let generated = 0;

    for (let i = 0; i < sampleSize; i++) {
      const item = generateItem(configs.items, configs.affixes, rarity, slot, ilvl, affixCounts, configs.item_names);
      if (!item) continue;
      generated++;

      // Track affix frequency
      for (const affix of item.affixes) {
        const key = affix.affix_id || affix.name;
        affixFreq[key] = (affixFreq[key] || { count: 0, name: affix.name, type: affix.type, stat: affix.stat });
        affixFreq[key].count++;
      }

      // Track stat totals
      for (const [stat, val] of Object.entries(item.stats)) {
        if (!statTotals[stat]) statTotals[stat] = { sum: 0, count: 0, min: Infinity, max: -Infinity };
        statTotals[stat].sum += val;
        statTotals[stat].count++;
        statTotals[stat].min = Math.min(statTotals[stat].min, val);
        statTotals[stat].max = Math.max(statTotals[stat].max, val);
      }

      // Track budget distribution
      budgets.push(calcBudget(item.stats, statsMeta));
    }

    // Compute averages
    for (const stat of Object.keys(statTotals)) {
      statTotals[stat].avg = statTotals[stat].sum / statTotals[stat].count;
    }

    // Sort affix frequency
    const sortedAffixes = Object.values(affixFreq).sort((a, b) => b.count - a.count);

    // Budget histogram (10 bins)
    const budgetMin = Math.min(...budgets);
    const budgetMax = Math.max(...budgets);
    const binSize = (budgetMax - budgetMin) / 10 || 1;
    const histogram = Array(10).fill(0);
    for (const b of budgets) {
      const bin = Math.min(9, Math.floor((b - budgetMin) / binSize));
      histogram[bin]++;
    }

    setResults({
      generated, sortedAffixes, statTotals, budgets,
      budgetMin, budgetMax, budgetAvg: budgets.reduce((a, b) => a + b, 0) / budgets.length,
      histogram, binSize,
    });
  }

  return (
    <div>
      <div className="filter-bar" style={{ flexWrap: 'wrap' }}>
        <div>
          <label style={{ fontSize: 11, color: 'var(--text-dim)' }}>Slot</label>
          <select value={slot} onChange={e => setSlot(e.target.value)}>
            <option value="any">Any</option>
            {(statsMeta?.equip_slots || []).map(s => (
              <option key={s} value={s}>{s}</option>
            ))}
          </select>
        </div>
        <div>
          <label style={{ fontSize: 11, color: 'var(--text-dim)' }}>Rarity</label>
          <select value={rarity} onChange={e => setRarity(e.target.value)}>
            {['common', 'magic', 'rare', 'epic'].map(r => <option key={r} value={r}>{r}</option>)}
          </select>
        </div>
        <div>
          <label style={{ fontSize: 11, color: 'var(--text-dim)' }}>iLvl</label>
          <input type="number" min={1} max={20} value={ilvl}
            onChange={e => setIlvl(parseInt(e.target.value) || 1)} style={{ width: 60 }} />
        </div>
        <div>
          <label style={{ fontSize: 11, color: 'var(--text-dim)' }}>Samples</label>
          <select value={sampleSize} onChange={e => setSampleSize(parseInt(e.target.value))}>
            {[100, 500, 1000, 5000, 10000].map(n => <option key={n} value={n}>{n.toLocaleString()}</option>)}
          </select>
        </div>
        <button className="btn btn-primary ml-auto" onClick={runSimulation}>
          📊 Run Simulation
        </button>
      </div>

      {!results && (
        <div className="empty-state">
          <p>Configure parameters and run a simulation to see affix distribution data.</p>
        </div>
      )}

      {results && (
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16, marginTop: 12 }}>
          {/* Affix Frequency */}
          <div className="card">
            <h4 style={{ margin: '0 0 8px', fontSize: 13, color: 'var(--accent)' }}>Affix Frequency</h4>
            <div style={{ fontSize: 11, color: 'var(--text-dim)', marginBottom: 8 }}>
              {results.generated.toLocaleString()} items generated
            </div>
            <div style={{ maxHeight: 300, overflowY: 'auto' }}>
              {results.sortedAffixes.map((a, i) => {
                const pct = (a.count / results.generated) * 100;
                return (
                  <div key={i} style={{ marginBottom: 4 }}>
                    <div className="flex-row" style={{ fontSize: 12 }}>
                      <span style={{
                        color: a.type === 'prefix' ? '#4488ff' : '#ffcc00',
                        fontWeight: 600, width: 120,
                      }}>{a.name}</span>
                      <span style={{ color: 'var(--text-dim)', fontSize: 10, width: 80 }}>{a.stat}</span>
                      <span style={{ fontFamily: 'var(--font-mono)', marginLeft: 'auto' }}>
                        {a.count} ({pct.toFixed(1)}%)
                      </span>
                    </div>
                    <div style={{ height: 3, background: 'var(--bg-dark)', borderRadius: 2 }}>
                      <div style={{
                        height: '100%', borderRadius: 2,
                        width: `${pct}%`,
                        background: a.type === 'prefix' ? '#4488ff' : '#ffcc00',
                      }} />
                    </div>
                  </div>
                );
              })}
            </div>
          </div>

          {/* Stat Averages */}
          <div className="card">
            <h4 style={{ margin: '0 0 8px', fontSize: 13, color: 'var(--accent)' }}>Stat Averages</h4>
            <table style={{ width: '100%', fontSize: 11 }}>
              <thead>
                <tr style={{ color: 'var(--text-dim)' }}>
                  <th style={{ textAlign: 'left' }}>Stat</th>
                  <th>Avg</th>
                  <th>Min</th>
                  <th>Max</th>
                  <th>Appear %</th>
                </tr>
              </thead>
              <tbody>
                {Object.entries(results.statTotals)
                  .sort((a, b) => b[1].count - a[1].count)
                  .map(([stat, data]) => {
                    const info = statsMeta?.stats?.[stat];
                    const fmt = v => info?.type === 'float' ? `${(v * 100).toFixed(1)}%` : Math.round(v);
                    return (
                      <tr key={stat}>
                        <td style={{ color: 'var(--text)' }}>{info?.label || stat}</td>
                        <td style={{ textAlign: 'center', fontFamily: 'var(--font-mono)', color: 'var(--success)' }}>{fmt(data.avg)}</td>
                        <td style={{ textAlign: 'center', fontFamily: 'var(--font-mono)' }}>{fmt(data.min)}</td>
                        <td style={{ textAlign: 'center', fontFamily: 'var(--font-mono)' }}>{fmt(data.max)}</td>
                        <td style={{ textAlign: 'center', fontFamily: 'var(--font-mono)' }}>
                          {((data.count / results.generated) * 100).toFixed(1)}%
                        </td>
                      </tr>
                    );
                  })}
              </tbody>
            </table>
          </div>

          {/* Budget Distribution */}
          <div className="card" style={{ gridColumn: 'span 2' }}>
            <h4 style={{ margin: '0 0 8px', fontSize: 13, color: 'var(--accent)' }}>
              Stat Budget Distribution
              <span style={{ fontWeight: 400, fontSize: 11, color: 'var(--text-dim)', marginLeft: 8 }}>
                avg: {results.budgetAvg.toFixed(1)} · min: {results.budgetMin.toFixed(1)} · max: {results.budgetMax.toFixed(1)}
              </span>
            </h4>
            <div style={{ display: 'flex', alignItems: 'flex-end', gap: 2, height: 120 }}>
              {results.histogram.map((count, i) => {
                const maxCount = Math.max(...results.histogram, 1);
                const height = (count / maxCount) * 100;
                const binStart = results.budgetMin + i * results.binSize;
                const binEnd = binStart + results.binSize;
                const range = statsMeta?.stat_budget_ranges?.[rarity];
                const inRange = range && binStart >= range.min && binEnd <= range.max;
                return (
                  <div key={i} style={{ flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
                    <div style={{ fontSize: 9, fontFamily: 'var(--font-mono)', color: 'var(--text-dim)', marginBottom: 2 }}>
                      {count}
                    </div>
                    <div style={{
                      width: '100%', height: `${height}%`, borderRadius: '3px 3px 0 0',
                      background: inRange ? 'var(--success)' : 'var(--warning)',
                      minHeight: count > 0 ? 2 : 0,
                    }} />
                    <div style={{ fontSize: 8, color: 'var(--text-dim)', marginTop: 2 }}>
                      {binStart.toFixed(0)}
                    </div>
                  </div>
                );
              })}
            </div>
            {statsMeta?.stat_budget_ranges?.[rarity] && (
              <div style={{ fontSize: 10, color: 'var(--text-dim)', marginTop: 4 }}>
                Target range for {rarity}: {statsMeta.stat_budget_ranges[rarity].min}–{statsMeta.stat_budget_ranges[rarity].max}
                <span style={{ color: 'var(--success)', marginLeft: 8 }}>■ In range</span>
                <span style={{ color: 'var(--warning)', marginLeft: 8 }}>■ Out of range</span>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

// ═════════════════════════════════════════════════════════
// Drop Rate Tab — floor/MF calculator
// ═════════════════════════════════════════════════════════
function DropRateTab({ configs, statsMeta }) {
  const [floor, setFloor] = useState(1);
  const [magicFind, setMagicFind] = useState(0);
  const [isBoss, setIsBoss] = useState(false);

  const loot = configs?.loot_tables?.rarity_config;
  const rarityColors = statsMeta?.rarity_colors || {};

  const rates = useMemo(() => {
    if (!loot) return null;

    const base = { ...loot.base_rates };

    // Floor bonus — shift weight from common to better rarities
    let floorBonus = 0;
    for (const [range, bonus] of Object.entries(loot.floor_bonuses || {})) {
      const [lo, hi] = range.replace('+', '').split('-').map(Number);
      if (floor >= lo && (isNaN(hi) || floor <= hi || range.includes('+'))) {
        floorBonus = bonus;
      }
    }

    // Apply floor bonus: reduce common, distribute to higher rarities
    const adjusted = { ...base };
    const commonReduction = base.common * floorBonus * 0.3; // 30% of floor bonus effect on common
    adjusted.common = Math.max(20, base.common - commonReduction);
    adjusted.magic += commonReduction * 0.4;
    adjusted.rare += commonReduction * 0.3;
    adjusted.epic += commonReduction * 0.2;
    adjusted.unique += commonReduction * 0.1;

    // Magic find bonus — multiplicative on non-common rates
    const mfMult = 1 + magicFind;
    adjusted.magic *= mfMult;
    adjusted.rare *= mfMult;
    adjusted.epic *= mfMult;
    adjusted.unique *= mfMult;

    // Normalize to 100%
    const total = Object.values(adjusted).reduce((s, v) => s + v, 0);
    const normalized = {};
    for (const [k, v] of Object.entries(adjusted)) {
      normalized[k] = (v / total) * 100;
    }

    // Boss guaranteed rarity
    let bossGuaranteed = null;
    if (isBoss) {
      for (const [range, rarity] of Object.entries(loot.boss_guaranteed_rarity || {})) {
        const [lo, hi] = range.replace('+', '').split('-').map(Number);
        if (floor >= lo && (isNaN(hi) || floor <= hi || range.includes('+'))) {
          bossGuaranteed = rarity;
        }
      }
    }

    // Boss unique chance
    const bossUniqueChance = isBoss && floor >= 8 ? (loot.boss_unique_chance_floor8 || 0.10) : 0;

    return { normalized, floorBonus, bossGuaranteed, bossUniqueChance };
  }, [loot, floor, magicFind, isBoss]);

  if (!loot) {
    return (
      <div className="empty-state">
        <p>No loot_tables.json found — cannot calculate drop rates.</p>
      </div>
    );
  }

  return (
    <div>
      <div className="filter-bar" style={{ flexWrap: 'wrap', alignItems: 'flex-end' }}>
        <div>
          <label style={{ fontSize: 11, color: 'var(--text-dim)' }}>Dungeon Floor</label>
          <input type="range" min={1} max={12} value={floor}
            onChange={e => setFloor(parseInt(e.target.value))} style={{ width: 120 }} />
          <span style={{ fontFamily: 'var(--font-mono)', marginLeft: 4 }}>F{floor}</span>
        </div>
        <div>
          <label style={{ fontSize: 11, color: 'var(--text-dim)' }}>Magic Find %</label>
          <input type="range" min={0} max={60} value={magicFind * 100}
            onChange={e => setMagicFind(parseInt(e.target.value) / 100)} style={{ width: 120 }} />
          <span style={{ fontFamily: 'var(--font-mono)', marginLeft: 4 }}>{(magicFind * 100).toFixed(0)}%</span>
        </div>
        <div>
          <label style={{ display: 'flex', alignItems: 'center', gap: 6, cursor: 'pointer', fontSize: 12 }}>
            <input type="checkbox" checked={isBoss} onChange={e => setIsBoss(e.target.checked)} />
            Boss Kill
          </label>
        </div>
      </div>

      {rates && (
        <div style={{ marginTop: 16 }}>
          {/* Rarity bar */}
          <div className="card">
            <h4 style={{ margin: '0 0 12px', fontSize: 13, color: 'var(--accent)' }}>
              Drop Rarity Distribution
            </h4>
            <div style={{ display: 'flex', height: 32, borderRadius: 'var(--radius-sm)', overflow: 'hidden', marginBottom: 12 }}>
              {Object.entries(rates.normalized).map(([rarity, pct]) => (
                <div key={rarity} style={{
                  width: `${pct}%`, background: rarityColors[rarity] || '#666',
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                  fontSize: pct > 5 ? 11 : 8, fontWeight: 600, color: '#000',
                  transition: 'width 0.3s ease',
                }}>
                  {pct > 3 ? `${pct.toFixed(1)}%` : ''}
                </div>
              ))}
            </div>

            {/* Rarity table */}
            <table style={{ width: '100%', fontSize: 12 }}>
              <thead>
                <tr style={{ color: 'var(--text-dim)' }}>
                  <th style={{ textAlign: 'left' }}>Rarity</th>
                  <th>Base %</th>
                  <th>Effective %</th>
                  <th>~1 in N drops</th>
                </tr>
              </thead>
              <tbody>
                {Object.entries(rates.normalized).map(([r, pct]) => (
                  <tr key={r}>
                    <td style={{ color: rarityColors[r], fontWeight: 600, textTransform: 'capitalize' }}>{r}</td>
                    <td style={{ textAlign: 'center', fontFamily: 'var(--font-mono)' }}>
                      {loot.base_rates[r]?.toFixed(1)}%
                    </td>
                    <td style={{ textAlign: 'center', fontFamily: 'var(--font-mono)', color: 'var(--success)' }}>
                      {pct.toFixed(2)}%
                    </td>
                    <td style={{ textAlign: 'center', fontFamily: 'var(--font-mono)' }}>
                      {pct > 0 ? `1 in ${Math.round(100 / pct)}` : '—'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* Boss info */}
          {isBoss && (
            <div className="card" style={{ marginTop: 12, borderLeft: '3px solid var(--accent)' }}>
              <h4 style={{ margin: '0 0 8px', fontSize: 13, color: 'var(--accent)' }}>Boss Kill Bonuses</h4>
              <div style={{ fontSize: 12 }}>
                {rates.bossGuaranteed && (
                  <div>
                    <span style={{ color: 'var(--text-dim)' }}>Guaranteed minimum rarity: </span>
                    <span style={{ color: rarityColors[rates.bossGuaranteed], fontWeight: 600 }}>
                      {rates.bossGuaranteed}
                    </span>
                  </div>
                )}
                {rates.bossUniqueChance > 0 && (
                  <div>
                    <span style={{ color: 'var(--text-dim)' }}>Unique drop chance: </span>
                    <span style={{ color: rarityColors.unique, fontWeight: 600 }}>
                      {(rates.bossUniqueChance * 100).toFixed(0)}%
                    </span>
                  </div>
                )}
                <div style={{ marginTop: 8 }}>
                  <span style={{ color: 'var(--text-dim)' }}>Drop count: </span>
                  {Object.entries(loot.boss_drop_counts || {}).map(([range, counts]) => {
                    const [lo, hi] = range.replace('+', '').split('-').map(Number);
                    const active = floor >= lo && (isNaN(hi) || floor <= hi || range.includes('+'));
                    return (
                      <span key={range} style={{
                        display: 'inline-block', padding: '2px 8px', borderRadius: 3, marginRight: 4,
                        fontSize: 11, fontFamily: 'var(--font-mono)',
                        background: active ? 'rgba(68,136,255,0.2)' : 'var(--bg-dark)',
                        color: active ? 'var(--accent)' : 'var(--text-dim)',
                        fontWeight: active ? 600 : 400,
                      }}>
                        F{range}: {counts.min}–{counts.max}
                      </span>
                    );
                  })}
                </div>
              </div>
            </div>
          )}

          {/* Floor bonus summary */}
          <div className="card" style={{ marginTop: 12 }}>
            <h4 style={{ margin: '0 0 8px', fontSize: 13, color: 'var(--accent)' }}>Floor Bonus Progression</h4>
            <div style={{ display: 'flex', gap: 4, flexWrap: 'wrap' }}>
              {Object.entries(loot.floor_bonuses || {}).map(([range, bonus]) => {
                const [lo] = range.replace('+', '').split('-').map(Number);
                const active = floor >= lo;
                return (
                  <div key={range} style={{
                    padding: '6px 12px', borderRadius: 'var(--radius-sm)',
                    background: active ? 'rgba(68,136,255,0.15)' : 'var(--bg-dark)',
                    border: `1px solid ${active ? 'var(--accent)' : 'var(--border)'}`,
                    textAlign: 'center', fontSize: 12,
                  }}>
                    <div style={{ fontWeight: 600, color: active ? 'var(--accent)' : 'var(--text-dim)' }}>F{range}</div>
                    <div style={{ fontFamily: 'var(--font-mono)', color: active ? 'var(--success)' : 'var(--text-dim)' }}>
                      +{(bonus * 100).toFixed(0)}%
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
