// ─────────────────────────────────────────────────────────
// RoomPanel.jsx — Detected rooms list + purpose assignment
// ─────────────────────────────────────────────────────────

import React from 'react';
import { ROOM_COLORS } from '../utils/tileColors.js';

const PURPOSES = ['empty', 'spawn', 'enemy', 'loot', 'boss', 'corridor'];

export default function RoomPanel({
  rooms,
  onRoomPurposeChange,
  onRoomNameChange,
  onRemoveSmallRooms,
  smallRoomThreshold,
  onSmallRoomThresholdChange,
}) {
  if (!rooms || rooms.length === 0) {
    return (
      <div className="panel room-panel">
        <h3 className="panel-title">Detected Rooms</h3>
        <p className="panel-empty">Generate a cave to detect rooms</p>
      </div>
    );
  }

  const totalFloor = rooms.reduce((s, r) => s + r.size, 0);

  return (
    <div className="panel room-panel">
      <h3 className="panel-title">Detected Rooms ({rooms.length})</h3>

      <div className="param-group">
        <label className="param-label">
          Min Room Size: {smallRoomThreshold}
          <input
            type="range"
            min={1}
            max={50}
            value={smallRoomThreshold}
            onChange={e => onSmallRoomThresholdChange(parseInt(e.target.value))}
            className="input-range"
          />
        </label>
        <button onClick={onRemoveSmallRooms} className="btn btn-secondary btn-full">
          Remove Small Rooms
        </button>
      </div>

      <div className="room-list">
        {rooms.map((room, idx) => (
          <div key={room.id} className="room-item">
            <div className="room-header">
              <span
                className="room-color-dot"
                style={{ background: ROOM_COLORS[idx % ROOM_COLORS.length].replace('0.25', '0.8') }}
              />
              <input
                type="text"
                value={room.name || `Chamber ${room.id + 1}`}
                onChange={e => onRoomNameChange(room.id, e.target.value)}
                className="input-text input-small"
                title="Room name"
              />
              <span className="room-size">{room.size} tiles</span>
            </div>
            <div className="room-controls">
              <select
                value={room.purpose || 'empty'}
                onChange={e => onRoomPurposeChange(room.id, e.target.value)}
                className="input-select input-small"
              >
                {PURPOSES.map(p => (
                  <option key={p} value={p}>{p.charAt(0).toUpperCase() + p.slice(1)}</option>
                ))}
              </select>
              <span className="room-percent">
                {((room.size / totalFloor) * 100).toFixed(1)}%
              </span>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
