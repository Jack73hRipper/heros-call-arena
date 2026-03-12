// ─────────────────────────────────────────────────────────
// SpawnPreview.jsx — Preview spawn rolls for a floor
// ─────────────────────────────────────────────────────────

import React, { useState, useCallback } from 'react';

function rollRarity(floor, spawnChances) {
  const {
    champion_base_chance = 0.08,
    rare_base_chance = 0.03,
    floor_bonus_per_level = 0.01,
    min_floor_for_champions = 1,
    min_floor_for_rares = 3,
  } = spawnChances;

  const floorBonus = (floor - 1) * floor_bonus_per_level;
  const rareChance = floor >= min_floor_for_rares ? rare_base_chance + floorBonus : 0;
  const champChance = floor >= min_floor_for_champions ? champion_base_chance + floorBonus : 0;

  const roll = Math.random();
  if (roll < rareChance) return 'rare';
  if (roll < rareChance + champChance) return 'champion';
  return 'normal';
}

function rollChampionType(championTypes) {
  const types = Object.keys(championTypes);
  return types[Math.floor(Math.random() * types.length)];
}

export default function SpawnPreview({ rarity, enemies, meta }) {
  const [floor, setFloor] = useState(3);
  const [numRolls, setNumRolls] = useState(200);
  const [results, setResults] = useState(null);

  const spawnChances = rarity?.spawn_chances || {};
  const championTypes = rarity?.champion_types || {};

  const runPreview = useCallback(() => {
    const counts = { normal: 0, champion: 0, rare: 0, super_unique: 0 };
    const champTypeCounts = {};
    Object.keys(championTypes).forEach(ct => { champTypeCounts[ct] = 0; });

    for (let i = 0; i < numRolls; i++) {
      const tier = rollRarity(floor, spawnChances);
      counts[tier]++;
      if (tier === 'champion') {
        const ct = rollChampionType(championTypes);
        champTypeCounts[ct] = (champTypeCounts[ct] || 0) + 1;
      }
    }

    setResults({ counts, champTypeCounts, total: numRolls });
  }, [floor, numRolls, spawnChances, championTypes]);

  return (
    <div className="spawn-preview">
      <div className="card mb-8">
        <h3>🎲 Spawn Preview</h3>
        <p className="text-dim" style={{ fontSize: 12 }}>
          Preview what rarity distribution looks like when spawning enemies for a specific floor.
        </p>
        <div className="form-row">
          <div className="form-group">
            <label>Floor Number</label>
            <input type="number" min="1" max="20" value={floor} onChange={e => setFloor(parseInt(e.target.value) || 1)} />
          </div>
          <div className="form-group">
            <label>Number of Rolls</label>
            <select value={numRolls} onChange={e => setNumRolls(parseInt(e.target.value))}>
              <option value="50">50</option>
              <option value="100">100</option>
              <option value="200">200</option>
              <option value="500">500</option>
              <option value="1000">1000</option>
            </select>
          </div>
          <div className="form-group" style={{ alignSelf: 'flex-end' }}>
            <button className="btn btn-primary" onClick={runPreview}>Generate</button>
          </div>
        </div>

        {/* Display effective chances */}
        <div className="stat-callout mt-12">
          <span>Floor Bonus: <strong>+{((floor - 1) * (spawnChances.floor_bonus_per_level || 0.01) * 100).toFixed(0)}%</strong></span>
          <span>Champion: <strong>{((spawnChances.champion_base_chance || 0.08) * 100 + (floor - 1) * (spawnChances.floor_bonus_per_level || 0.01) * 100).toFixed(1)}%</strong></span>
          <span>Rare: <strong>{floor >= (spawnChances.min_floor_for_rares || 3) ? ((spawnChances.rare_base_chance || 0.03) * 100 + (floor - 1) * (spawnChances.floor_bonus_per_level || 0.01) * 100).toFixed(1) : '0'}%</strong></span>
        </div>
      </div>

      {results && (
        <>
          {/* Pie Chart (simple bar representation) */}
          <div className="card mb-8">
            <h4>Distribution ({results.total} spawns)</h4>
            <div className="dist-chart">
              {Object.entries(results.counts)
                .filter(([, count]) => count > 0 || true)
                .map(([tier, count]) => {
                  const pct = (count / results.total) * 100;
                  const colors = {
                    normal: '#666',
                    champion: '#6688ff',
                    rare: '#ffcc00',
                    super_unique: '#cc66ff',
                  };
                  return (
                    <div key={tier} className="dist-bar-row">
                      <div className="dist-bar-label" style={{ color: colors[tier] }}>
                        {tier}
                      </div>
                      <div className="dist-bar-track">
                        <div
                          className="dist-bar-fill"
                          style={{ width: `${pct}%`, background: colors[tier] }}
                        />
                      </div>
                      <div className="dist-bar-value">
                        {count} ({pct.toFixed(1)}%)
                      </div>
                    </div>
                  );
                })}
            </div>
          </div>

          {/* Champion Type Breakdown */}
          {results.counts.champion > 0 && (
            <div className="card mb-8">
              <h4>Champion Type Breakdown ({results.counts.champion} champions)</h4>
              <div className="dist-chart">
                {Object.entries(results.champTypeCounts)
                  .filter(([, c]) => c > 0)
                  .sort((a, b) => b[1] - a[1])
                  .map(([ctId, count]) => {
                    const pct = (count / results.counts.champion) * 100;
                    const tintColor = championTypes[ctId]?.visual_tint || '#888';
                    return (
                      <div key={ctId} className="dist-bar-row">
                        <div className="dist-bar-label" style={{ color: tintColor }}>
                          {ctId}
                        </div>
                        <div className="dist-bar-track">
                          <div
                            className="dist-bar-fill"
                            style={{ width: `${pct}%`, background: tintColor }}
                          />
                        </div>
                        <div className="dist-bar-value">
                          {count} ({pct.toFixed(1)}%)
                        </div>
                      </div>
                    );
                  })}
              </div>
            </div>
          )}

          {/* Summary table */}
          <div className="card">
            <h4>Summary</h4>
            <table className="data-table">
              <thead>
                <tr>
                  <th>Tier</th>
                  <th>Count</th>
                  <th>%</th>
                  <th>Expected</th>
                </tr>
              </thead>
              <tbody>
                {Object.entries(results.counts).map(([tier, count]) => {
                  const pct = (count / results.total) * 100;
                  let expected = '—';
                  if (tier === 'normal') expected = `~${(100 - ((spawnChances.champion_base_chance || 0.08) * 100 + (floor - 1) * (spawnChances.floor_bonus_per_level || 0.01) * 100 + (floor >= (spawnChances.min_floor_for_rares || 3) ? (spawnChances.rare_base_chance || 0.03) * 100 + (floor - 1) * (spawnChances.floor_bonus_per_level || 0.01) * 100 : 0))).toFixed(0)}%`;
                  if (tier === 'champion') expected = `~${((spawnChances.champion_base_chance || 0.08) * 100 + (floor - 1) * (spawnChances.floor_bonus_per_level || 0.01) * 100).toFixed(0)}%`;
                  if (tier === 'rare') expected = floor >= (spawnChances.min_floor_for_rares || 3) ? `~${((spawnChances.rare_base_chance || 0.03) * 100 + (floor - 1) * (spawnChances.floor_bonus_per_level || 0.01) * 100).toFixed(0)}%` : '0%';
                  if (tier === 'super_unique') expected = 'Per-floor (25%)';

                  return (
                    <tr key={tier}>
                      <td style={{ color: meta?.rarity_colors?.[tier] || '#fff' }}>{tier}</td>
                      <td className="mono">{count}</td>
                      <td className="mono">{pct.toFixed(1)}%</td>
                      <td className="text-dim">{expected}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </>
      )}

      {!results && (
        <div className="empty-state">
          <h3>Generate Spawn Data</h3>
          <p>Select a floor and number of rolls, then click Generate to preview the rarity distribution.</p>
        </div>
      )}
    </div>
  );
}
