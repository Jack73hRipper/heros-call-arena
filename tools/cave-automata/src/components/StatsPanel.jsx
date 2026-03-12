// ─────────────────────────────────────────────────────────
// StatsPanel.jsx — Map statistics display
// ─────────────────────────────────────────────────────────

import React from 'react';

export default function StatsPanel({ tileMap, rooms, connectivityInfo }) {
  if (!tileMap || tileMap.length === 0) return null;

  const height = tileMap.length;
  const width = tileMap[0]?.length || 0;
  const totalCells = width * height;

  // Count tile types
  const counts = {};
  for (let y = 0; y < height; y++) {
    for (let x = 0; x < width; x++) {
      const t = tileMap[y][x];
      counts[t] = (counts[t] || 0) + 1;
    }
  }

  const floorCount = (counts['F'] || 0) + (counts['C'] || 0) + (counts['S'] || 0) +
                     (counts['X'] || 0) + (counts['E'] || 0) + (counts['B'] || 0) +
                     (counts['D'] || 0);
  const wallCount = counts['W'] || 0;

  const largestRoom = rooms && rooms.length > 0 ? rooms[0].size : 0;
  const smallestRoom = rooms && rooms.length > 0 ? rooms[rooms.length - 1].size : 0;

  return (
    <div className="panel stats-panel">
      <h3 className="panel-title">Statistics</h3>

      <div className="stat-grid">
        <div className="stat-item">
          <span className="stat-label">Dimensions</span>
          <span className="stat-value">{width} x {height}</span>
        </div>
        <div className="stat-item">
          <span className="stat-label">Total Cells</span>
          <span className="stat-value">{totalCells}</span>
        </div>
        <div className="stat-item">
          <span className="stat-label">Floor %</span>
          <span className="stat-value">{((floorCount / totalCells) * 100).toFixed(1)}%</span>
        </div>
        <div className="stat-item">
          <span className="stat-label">Wall %</span>
          <span className="stat-value">{((wallCount / totalCells) * 100).toFixed(1)}%</span>
        </div>
        <div className="stat-item">
          <span className="stat-label">Regions</span>
          <span className="stat-value">{connectivityInfo ? connectivityInfo.regionCount : '—'}</span>
        </div>
        <div className="stat-item">
          <span className="stat-label">Connected</span>
          <span className={`stat-value ${connectivityInfo?.connected ? 'stat-good' : 'stat-warn'}`}>
            {connectivityInfo ? (connectivityInfo.connected ? 'Yes' : 'No') : '—'}
          </span>
        </div>
        <div className="stat-item">
          <span className="stat-label">Largest Room</span>
          <span className="stat-value">{largestRoom} tiles</span>
        </div>
        <div className="stat-item">
          <span className="stat-label">Smallest Room</span>
          <span className="stat-value">{smallestRoom} tiles</span>
        </div>

        {counts['S'] > 0 && (
          <div className="stat-item">
            <span className="stat-label">Spawn Points</span>
            <span className="stat-value">{counts['S']}</span>
          </div>
        )}
        {counts['E'] > 0 && (
          <div className="stat-item">
            <span className="stat-label">Enemy Spawns</span>
            <span className="stat-value">{counts['E']}</span>
          </div>
        )}
        {counts['B'] > 0 && (
          <div className="stat-item">
            <span className="stat-label">Boss Spawns</span>
            <span className="stat-value">{counts['B']}</span>
          </div>
        )}
        {counts['X'] > 0 && (
          <div className="stat-item">
            <span className="stat-label">Chests</span>
            <span className="stat-value">{counts['X']}</span>
          </div>
        )}
        {counts['D'] > 0 && (
          <div className="stat-item">
            <span className="stat-label">Doors</span>
            <span className="stat-value">{counts['D']}</span>
          </div>
        )}
      </div>
    </div>
  );
}
