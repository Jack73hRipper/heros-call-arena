import React, { useEffect, useRef, useMemo, useState, useCallback } from 'react';
import { useGameState } from '../../context/GameStateContext';
import { LOG_ICONS, LOG_FILTER_CATEGORIES } from '../../utils/combatLogBuilder';

/**
 * CombatLog — Scrolling feed of turn results with color-coded, icon-prefixed messages.
 *
 * Phase CL (Combat Log Overhaul):
 *  - Turn separators visually divide turns
 *  - Icons per message type for quick scanning
 *  - Filter tabs (All / Combat / Skills / Loot / Events)
 *  - Collapsed duplicate messages shown as "message (×N)"
 *
 * Phase 18E (E9): Enhanced enemy names rendered in rarity color.
 */

const LOG_COLORS = {
  'damage': '#f44',
  'kill': '#ff6a30',
  'miss': '#666',
  'system': '#888',
  'ranged_attack': '#ffaa00',
  'cooldown': '#aa88ff',
  'boss_kill': '#ff44ff',
  'enemy_spawn': '#e84040',
  'room_cleared': '#4af59f',
  'loot': '#daa520',
  'heal': '#44dd44',
  'dot_damage': '#ff6666',
  'hot_heal': '#88ffaa',
  'holy_damage': '#ffd700',
  'shield_reflect': '#44ddff',
  'detection': '#dd88ff',
  'buff': '#80e0a0',
  'skill': '#cc88ff',
  'interact': '#c8b070',
  'potion': '#ff88aa',
  'portal': '#cc66ff',
  'elite_kill': '#ffcc00',
  'wave': '#ff8844',
  'death': '#ff4444',
  'dodge': '#66ccff',
  'stunned': '#ffcc00',
  'slowed': '#6688ff',
};

/** Phase 18E (E9): Rarity name colors for combat log colorization */
const RARITY_LOG_COLORS = {
  champion:     '#6688ff',
  rare:         '#ffcc00',
  super_unique: '#cc66ff',
};

/** Filter tab keys in render order */
const FILTER_KEYS = ['all', 'combat', 'skills', 'loot', 'events'];

/**
 * Phase 18E (E9): Colorize entity names in a combat log message.
 * Scans the message for known enhanced enemy names and wraps them
 * in colored <span> elements matching their rarity tier.
 *
 * @param {string} message - Plain text log message
 * @param {Array<{name: string, color: string}>} coloredNames - Sorted by name length desc
 * @returns {React.ReactNode} - Text with colored name spans
 */
function colorizeMessage(message, coloredNames) {
  if (!message || coloredNames.length === 0) return message;

  // Build segments by scanning for each colored name
  let segments = [{ text: message, isColored: false }];

  for (const { name, color } of coloredNames) {
    const newSegments = [];
    for (const seg of segments) {
      if (seg.isColored) {
        newSegments.push(seg);
        continue;
      }
      // Split plain text on occurrences of this name
      const parts = seg.text.split(name);
      for (let i = 0; i < parts.length; i++) {
        if (parts[i]) newSegments.push({ text: parts[i], isColored: false });
        if (i < parts.length - 1) {
          newSegments.push({ text: name, isColored: true, color });
        }
      }
    }
    segments = newSegments;
  }

  // If nothing was colored, return plain string (avoids unnecessary spans)
  if (!segments.some(s => s.isColored)) return message;

  return segments.map((seg, i) =>
    seg.isColored
      ? <span key={i} style={{ color: seg.color, fontWeight: 'bold' }}>{seg.text}</span>
      : <span key={i}>{seg.text}</span>
  );
}

export default function CombatLog() {
  const { combatLog, players } = useGameState();
  const scrollRef = useRef(null);
  const [activeFilter, setActiveFilter] = useState('all');

  // Phase 18E (E9): Build a list of enhanced enemy names → rarity colors from current player state.
  // Sorted longest-first so "Blazing Skeleton the Pyreborn" matches before "Skeleton".
  const coloredNames = useMemo(() => {
    if (!players) return [];
    const entries = [];
    for (const p of Object.values(players)) {
      const rarity = p.monster_rarity;
      if (!rarity || rarity === 'normal') continue;
      const color = RARITY_LOG_COLORS[rarity];
      if (!color) continue;
      // Use display_name (generated/fixed name) or username
      const name = p.display_name || p.username;
      if (name) entries.push({ name, color });
    }
    // Sort longest first to match full names before partial matches
    entries.sort((a, b) => b.name.length - a.name.length);
    return entries;
  }, [players]);

  // Filter entries based on active tab
  const filteredLog = useMemo(() => {
    const filterDef = LOG_FILTER_CATEGORIES[activeFilter];
    if (!filterDef || !filterDef.types) return combatLog; // "all" tab
    return combatLog.filter(entry =>
      entry.type === 'turn_separator' || filterDef.types.has(entry.type)
    );
  }, [combatLog, activeFilter]);

  // Strip leading turn separators and consecutive separators after filtering
  const cleanedLog = useMemo(() => {
    const result = [];
    for (let i = 0; i < filteredLog.length; i++) {
      const entry = filteredLog[i];
      if (entry.type === 'turn_separator') {
        // Skip if this separator has no content entries after it (in this filter)
        const next = filteredLog[i + 1];
        if (!next || next.type === 'turn_separator') continue;
      }
      result.push(entry);
    }
    return result;
  }, [filteredLog]);

  // Auto-scroll to bottom on new entries
  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [cleanedLog]);

  const handleFilterClick = useCallback((key) => {
    setActiveFilter(key);
  }, []);

  return (
    <div className="combat-log">
      <div className="combat-log-header">
        <h3>Combat Log</h3>
        <div className="combat-log-filters">
          {FILTER_KEYS.map(key => (
            <button
              key={key}
              className={`log-filter-btn${activeFilter === key ? ' active' : ''}`}
              onClick={() => handleFilterClick(key)}
            >
              {LOG_FILTER_CATEGORIES[key].label}
            </button>
          ))}
        </div>
      </div>
      <div className="combat-log-entries" ref={scrollRef}>
        {cleanedLog.length === 0 ? (
          <p className="placeholder">Waiting for combat...</p>
        ) : (
          cleanedLog.map((entry, i) => {
            // Turn separator row
            if (entry.type === 'turn_separator') {
              return (
                <div key={`sep-${entry.turn}-${i}`} className="log-turn-separator">
                  {entry.message}
                </div>
              );
            }

            const icon = LOG_ICONS[entry.type] || LOG_ICONS.system;
            return (
              <p
                key={i}
                className={`log-entry log-${entry.type || 'system'}`}
                style={{ color: LOG_COLORS[entry.type] || '#ccc' }}
              >
                <span className="log-icon">{icon}</span>
                {' '}
                {colorizeMessage(entry.message, coloredNames)}
              </p>
            );
          })
        )}
      </div>
    </div>
  );
}
