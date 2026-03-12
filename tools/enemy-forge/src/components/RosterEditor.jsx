// ─────────────────────────────────────────────────────────
// RosterEditor.jsx — Floor enemy roster weight editor
// ─────────────────────────────────────────────────────────

import React, { useState, useMemo } from 'react';

const POOL_LABELS = {
  regular: '⚔️ Regular',
  boss:    '💀 Boss',
  support: '💚 Support',
};

const POOL_COLORS = {
  regular: 'var(--accent)',
  boss:    'var(--danger)',
  support: 'var(--success)',
};

function floorLabel(tier, idx, tiers) {
  const prevMax = idx > 0 ? tiers[idx - 1].max_floor + 1 : 1;
  const curMax = tier.max_floor;
  if (curMax >= 99) return `Floors ${prevMax}+`;
  return `Floors ${prevMax}–${curMax}`;
}

export default function RosterEditor({ roster, enemies, meta }) {
  const [selectedTier, setSelectedTier] = useState(0);

  const tiers = roster?.tiers || [];

  if (tiers.length === 0) {
    return (
      <div className="empty-state">
        <h3>No Roster Data</h3>
        <p>Could not load floor enemy roster from dungeon_generator.py</p>
      </div>
    );
  }

  const tier = tiers[selectedTier];
  const pools = tier?.pools || {};

  return (
    <div className="roster-editor">
      {/* Tier Selector */}
      <div className="roster-tier-tabs">
        {tiers.map((t, i) => (
          <button
            key={i}
            className={`btn ${selectedTier === i ? 'btn-primary' : ''}`}
            onClick={() => setSelectedTier(i)}
          >
            {floorLabel(t, i, tiers)}
          </button>
        ))}
      </div>

      {/* Pool Panels */}
      <div className="roster-pools">
        {Object.entries(POOL_LABELS).map(([poolKey, poolLabel]) => {
          const entries = pools[poolKey] || [];
          const totalWeight = entries.reduce((sum, e) => sum + e.weight, 0);

          return (
            <div key={poolKey} className="card mb-8">
              <div className="flex-row" style={{ justifyContent: 'space-between', marginBottom: 12 }}>
                <h4>{poolLabel}</h4>
                <span className="text-dim" style={{ fontSize: 12 }}>
                  Total weight: {totalWeight.toFixed(2)}
                  {Math.abs(totalWeight - 1.0) > 0.01 && (
                    <span style={{ color: 'var(--warning)', marginLeft: 6 }}>
                      ⚠️ Not normalized!
                    </span>
                  )}
                </span>
              </div>

              {/* Weight bar visualization */}
              <div className="weight-bar">
                {entries.map((entry, i) => {
                  const pct = totalWeight > 0 ? (entry.weight / totalWeight) * 100 : 0;
                  const enemyData = enemies[entry.enemy_type];
                  return (
                    <div
                      key={i}
                      className="weight-segment"
                      style={{
                        width: `${pct}%`,
                        background: enemyData?.color || '#555',
                      }}
                    >
                      <div className="weight-segment-tooltip">
                        {entry.enemy_type}: {(pct).toFixed(1)}%
                      </div>
                    </div>
                  );
                })}
              </div>

              {/* Detail table */}
              <table className="data-table mt-12">
                <thead>
                  <tr>
                    <th></th>
                    <th>Enemy Type</th>
                    <th>Name</th>
                    <th>role</th>
                    <th>Weight</th>
                    <th>%</th>
                    <th>HP</th>
                    <th>Damage</th>
                  </tr>
                </thead>
                <tbody>
                  {entries.map((entry, i) => {
                    const ed = enemies[entry.enemy_type];
                    const pct = totalWeight > 0 ? (entry.weight / totalWeight) * 100 : 0;
                    return (
                      <tr key={i}>
                        <td>
                          <div className="enemy-color-dot" style={{ background: ed?.color || '#555' }} />
                        </td>
                        <td className="mono">{entry.enemy_type}</td>
                        <td>{ed?.name || '?'}</td>
                        <td className="text-dim">{ed?.role || '?'}</td>
                        <td className="mono">{entry.weight.toFixed(2)}</td>
                        <td className="mono">{pct.toFixed(1)}%</td>
                        <td className="mono">{ed?.base_hp || '?'}</td>
                        <td className="mono">
                          {ed?.base_melee_damage || 0}/{ed?.base_ranged_damage || 0}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          );
        })}
      </div>

      <div className="card">
        <h4>📋 Roster Summary</h4>
        <p className="text-dim" style={{ fontSize: 12 }}>
          The floor enemy roster is defined in <code>server/app/core/wfc/dungeon_generator.py</code> as
          the <code>_FLOOR_ENEMY_ROSTER</code> constant. This view is read-only — edit the Python source
          directly to modify roster weights, then reload.
        </p>
        <p className="text-dim" style={{ fontSize: 12 }}>
          {tiers.length} floor tiers defined across {tiers.length} brackets.
          Total unique enemy types in rosters:{' '}
          {new Set(tiers.flatMap(t => Object.values(t.pools).flatMap(p => p.map(e => e.enemy_type)))).size}
        </p>
      </div>
    </div>
  );
}
