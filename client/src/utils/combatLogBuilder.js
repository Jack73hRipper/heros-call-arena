/**
 * combatLogBuilder.js — Extracted combat log entry builder.
 *
 * Builds typed log entries and damage floaters from TURN_RESULT action data.
 * Extracted from combatReducer.js for clarity and testability.
 *
 * Also provides:
 *  - LOG_MAX_ENTRIES: cap for log array length
 *  - LOG_ICONS: type → emoji icon map
 *  - LOG_FILTER_CATEGORIES: filter tab definitions
 *  - appendAndCapLog(): append entries with turn separator + cap
 *  - collapseLogEntries(): collapse consecutive duplicate messages
 */

// ── Constants ──────────────────────────────────────────────────────────────────

/** Maximum number of log entries kept in state (older entries are pruned). */
export const LOG_MAX_ENTRIES = 200;

/** Icons prepended to log messages by type for visual scanning. */
export const LOG_ICONS = {
  damage:         '⚔️',
  ranged_attack:  '🏹',
  kill:           '💀',
  boss_kill:      '👑',
  elite_kill:     '🔱',
  miss:           '◌',
  dodge:          '💨',
  stunned:        '⚡',
  slowed:         '🧊',
  heal:           '💚',
  hot_heal:       '🌿',
  dot_damage:     '🩸',
  holy_damage:    '✨',
  shield_reflect: '🛡️',
  detection:      '👁️',
  buff:           '🔺',
  skill:          '🔮',
  loot:           '💰',
  interact:       '🚪',
  potion:         '🧪',
  portal:         '🌀',
  wave:           '⚔️',
  system:         '▸',
  death:          '☠️',
  room_cleared:   '✅',
  enemy_spawn:    '🔴',
  cooldown:       '⏳',
};

/** Filter categories for the combat log UI tabs. */
export const LOG_FILTER_CATEGORIES = {
  all:    { label: 'All',    types: null }, // null = show everything
  combat: { label: 'Combat', types: new Set([
    'damage', 'ranged_attack', 'kill', 'boss_kill', 'elite_kill',
    'miss', 'dodge', 'stunned', 'slowed', 'holy_damage',
    'dot_damage', 'shield_reflect',
  ])},
  skills: { label: 'Skills', types: new Set([
    'skill', 'buff', 'heal', 'hot_heal', 'detection', 'potion',
  ])},
  loot:   { label: 'Loot',   types: new Set([
    'loot', 'interact',
  ])},
  events: { label: 'Events', types: new Set([
    'system', 'portal', 'wave', 'room_cleared', 'enemy_spawn',
    'death', 'cooldown', 'turn_separator',
  ])},
};

// ── Log entry classification ───────────────────────────────────────────────────

/**
 * Classify one action into a log entry type string.
 * Pure function — no side effects.
 */
function classifyAction(act, updatedPlayers) {
  // Successful attack / ranged_attack
  if ((act.action_type === 'attack' || act.action_type === 'ranged_attack') && act.success) {
    const targetData = act.target_id && updatedPlayers ? updatedPlayers[act.target_id] : null;
    const isBossKill = act.killed && targetData && targetData.is_boss;
    return act.killed ? (isBossKill ? 'boss_kill' : 'kill') : 'damage';
  }

  // Successful skill
  if (act.action_type === 'skill' && act.success) {
    // Ward reflect
    if (act.skill_id === 'ward' && act.message && act.message.includes('reflects')) {
      return 'shield_reflect';
    }
    if (act.heal_amount) {
      return act.is_tick ? 'hot_heal' : 'heal';
    }
    if (act.buff_applied) {
      const buffType = act.buff_applied?.type;
      if (buffType === 'dot')            return 'dot_damage';
      if (buffType === 'hot')            return 'hot_heal';
      if (buffType === 'shield_charges') return 'shield_reflect';
      if (buffType === 'detection')      return 'detection';
      if (act.buff_applied?.stat === 'armor') return 'buff';
      return 'system';
    }
    if (act.killed) {
      const targetData = act.target_id && updatedPlayers ? updatedPlayers[act.target_id] : null;
      return (act.killed && targetData && targetData.is_boss) ? 'boss_kill' : 'kill';
    }
    if (act.damage_dealt) {
      if (act.is_tick) return 'dot_damage';
      const holySkills = ['rebuke', 'exorcism'];
      return holySkills.includes(act.skill_id) ? 'holy_damage' : 'damage';
    }
    return 'skill';
  }

  // Failed attack/skill
  if (!act.success && (act.action_type === 'attack' || act.action_type === 'ranged_attack'
       || act.action_type === 'skill')) {
    const msg = (act.message || '').toLowerCase();
    if (msg.includes('dodged') || msg.includes('evaded')) return 'dodge';
    if (msg.includes('stunned'))  return 'stunned';
    if (msg.includes('slowed'))   return 'slowed';
    return 'miss';
  }

  if (act.action_type === 'loot' && act.success)     return 'loot';
  if (act.action_type === 'use_item' && act.success)  return 'potion';
  if (act.action_type === 'interact' && act.success)   return 'interact';
  if (!act.success) return 'miss';
  return 'system';
}

// ── Floater builder ────────────────────────────────────────────────────────────

/**
 * Build a damage/status floater for one action (if applicable).
 * Returns a floater object or null.
 */
function buildFloater(act, logType, turnNumber, updatedPlayers) {
  const now = Date.now();

  // Successful damage attacks → damage floater
  if ((act.action_type === 'attack' || act.action_type === 'ranged_attack')
      && act.success && act.target_id && act.damage_dealt && updatedPlayers) {
    const target = updatedPlayers[act.target_id];
    if (target) {
      return {
        id: `${turnNumber}-${act.player_id}-${act.target_id}`,
        x: target.position.x, y: target.position.y,
        text: `-${act.damage_dealt}`,
        color: act.action_type === 'ranged_attack'
          ? (act.killed ? '#ff8800' : '#ffaa00')
          : (act.killed ? '#ff8800' : '#ff4444'),
        damageAmount: act.damage_dealt, isKill: !!act.killed, createdAt: now,
      };
    }
  }

  // Skill heals → heal floater
  if (act.action_type === 'skill' && act.success && act.heal_amount) {
    const healTarget = act.target_id && updatedPlayers ? updatedPlayers[act.target_id] : null;
    if (healTarget) {
      const isTickHeal = !!act.is_tick;
      return {
        id: `${turnNumber}-${act.player_id}-heal-${act.target_id}`,
        x: healTarget.position.x, y: healTarget.position.y,
        text: `+${act.heal_amount}`,
        color: isTickHeal ? '#88ddaa' : '#44ff44',
        isTick: isTickHeal, createdAt: now,
      };
    }
  }

  // Skill damage → damage floater
  if (act.action_type === 'skill' && act.success && act.damage_dealt
      && act.target_id && updatedPlayers) {
    const skillTarget = updatedPlayers[act.target_id];
    if (skillTarget) {
      const isTickDmg = !!act.is_tick;
      return {
        id: `${turnNumber}-${act.player_id}-skill-${act.target_id}`,
        x: skillTarget.position.x, y: skillTarget.position.y,
        text: `-${act.damage_dealt}`,
        color: act.killed ? '#ff8800' : (isTickDmg ? '#aa66dd' : '#cc66ff'),
        isTick: isTickDmg, damageAmount: act.damage_dealt, isKill: !!act.killed, createdAt: now,
      };
    }
  }

  // Ward reflect → REFLECT floater
  if (act.action_type === 'skill' && act.success && act.skill_id === 'ward'
      && act.message && act.message.includes('reflects')
      && act.target_id && updatedPlayers) {
    const reflectTarget = updatedPlayers[act.target_id];
    if (reflectTarget) {
      return {
        id: `${turnNumber}-${act.player_id}-reflect-${act.target_id}`,
        x: reflectTarget.position.x, y: reflectTarget.position.y,
        text: 'REFLECT', color: '#cc88ff', isStatus: true, createdAt: now,
      };
    }
  }

  // Status floaters for failed actions
  if (!act.success && (act.action_type === 'attack' || act.action_type === 'ranged_attack'
       || act.action_type === 'skill')) {
    const msg = (act.message || '').toLowerCase();
    if ((msg.includes('dodged') || msg.includes('evaded')) && act.target_id && updatedPlayers) {
      const dodger = updatedPlayers[act.target_id];
      if (dodger) {
        return {
          id: `${turnNumber}-${act.player_id}-dodge-${act.target_id}`,
          x: dodger.position.x, y: dodger.position.y,
          text: 'DODGE', color: '#66ccff', isStatus: true, createdAt: now,
        };
      }
    }
    if (msg.includes('stunned') && act.player_id && updatedPlayers) {
      const stunned = updatedPlayers[act.player_id];
      if (stunned) {
        return {
          id: `${turnNumber}-${act.player_id}-stunned`,
          x: stunned.position.x, y: stunned.position.y,
          text: 'STUNNED', color: '#ffcc00', isStatus: true, createdAt: now,
        };
      }
    }
    if (msg.includes('slowed') && act.player_id && updatedPlayers) {
      const slowed = updatedPlayers[act.player_id];
      if (slowed) {
        return {
          id: `${turnNumber}-${act.player_id}-slowed`,
          x: slowed.position.x, y: slowed.position.y,
          text: 'SLOWED', color: '#6688ff', isStatus: true, createdAt: now,
        };
      }
    }
    // Generic MISS
    if (logType === 'miss' && act.target_id && updatedPlayers) {
      const missTarget = updatedPlayers[act.target_id];
      if (missTarget) {
        return {
          id: `${turnNumber}-${act.player_id}-miss-${act.target_id}`,
          x: missTarget.position.x, y: missTarget.position.y,
          text: 'MISS', color: '#999999', isStatus: true, createdAt: now,
        };
      }
    }
  }

  return null;
}

// ── Main builder ───────────────────────────────────────────────────────────────

/**
 * Build log entries and floaters from a TURN_RESULT payload.
 *
 * @param {object} payload - The TURN_RESULT action.payload
 * @param {object} state   - Current reducer state (for playerId, partyMembers)
 * @param {object} updatedPlayers - The new players dict from the payload
 * @returns {{ logEntries: Array, floaters: Array }}
 */
export function buildTurnLogEntries(payload, state, updatedPlayers) {
  const { turn_number, actions, loot_drops, chest_opened, items_picked_up, items_used } = payload;

  const logEntries = [];
  const floaters = [];

  // ── Action entries + floaters ──
  for (const act of (actions || [])) {
    if (act.action_type === 'wait') continue;
    if (act.action_type === 'move') continue;
    // Skip failed actions from AI units (not useful to the player)
    if (!act.success && act.player_id !== state.playerId
        && !(state.partyMembers || []).some(m => m.unit_id === act.player_id)) continue;

    const logType = classifyAction(act, updatedPlayers);
    logEntries.push({ message: act.message, type: logType });

    const floater = buildFloater(act, logType, turn_number, updatedPlayers);
    if (floater) floaters.push(floater);
  }

  // ── Loot events ──
  if (loot_drops && loot_drops.length > 0) {
    for (const drop of loot_drops) {
      const itemNames = drop.items?.map(i => i.name).join(', ') || 'items';
      logEntries.push({ message: `Loot dropped: ${itemNames}`, type: 'loot' });
    }
  }
  if (chest_opened && chest_opened.length > 0) {
    for (const co of chest_opened) {
      const itemNames = co.added_to_inventory?.map(i => i.name).join(', ') || '';
      logEntries.push({ message: `Chest opened! ${itemNames ? 'Found: ' + itemNames : ''}`, type: 'loot' });
    }
  }
  if (items_picked_up && items_picked_up.length > 0) {
    for (const pu of items_picked_up) {
      const itemNames = pu.items?.map(i => i.name).join(', ') || 'items';
      logEntries.push({ message: `Picked up: ${itemNames}`, type: 'loot' });
    }
  }
  if (items_used && items_used.length > 0) {
    for (const iu of items_used) {
      if (iu.effect?.actual_healed) {
        logEntries.push({ message: `Used ${iu.item_name || 'potion'} — healed ${iu.effect.actual_healed} HP`, type: 'heal' });
      }
    }
  }

  // ── Portal / extraction ──
  if (payload.extractions && payload.extractions.length > 0) {
    for (const ext of payload.extractions) {
      logEntries.push({ message: `${ext.username} escaped through the portal!`, type: 'portal' });
    }
  }
  if (payload.portal_spawned) {
    logEntries.push({ message: 'A shimmering portal tears open!', type: 'portal' });
  }
  if (payload.portal_expired) {
    logEntries.push({ message: 'The portal flickers and fades away...', type: 'portal' });
  }

  // ── Elite kills ──
  if (payload.elite_kills && payload.elite_kills.length > 0) {
    for (const ek of payload.elite_kills) {
      logEntries.push({ message: `${ek.display_name} has been vanquished!`, type: 'elite_kill' });
    }
  }

  return { logEntries, floaters };
}

// ── Log helpers ────────────────────────────────────────────────────────────────

/**
 * Collapse consecutive log entries with identical messages into "message (×N)".
 * Preserves entry type from the first occurrence.
 */
export function collapseLogEntries(entries) {
  if (entries.length <= 1) return entries;
  const collapsed = [];
  let i = 0;
  while (i < entries.length) {
    const current = entries[i];
    // Don't collapse separators or system messages
    if (current.type === 'turn_separator') {
      collapsed.push(current);
      i++;
      continue;
    }
    let count = 1;
    while (i + count < entries.length
           && entries[i + count].message === current.message
           && entries[i + count].type === current.type
           && entries[i + count].type !== 'turn_separator') {
      count++;
    }
    if (count > 1) {
      collapsed.push({ ...current, message: `${current.message} (×${count})`, count });
    } else {
      collapsed.push(current);
    }
    i += count;
  }
  return collapsed;
}

/**
 * Append new log entries to existing log with a turn separator, then cap length.
 *
 * @param {Array} existingLog - Current combatLog array
 * @param {Array} newEntries  - Entries from this turn
 * @param {number} turnNumber - Current turn number (for separator label)
 * @returns {Array} New capped log array
 */
export function appendAndCapLog(existingLog, newEntries, turnNumber) {
  if (newEntries.length === 0) return existingLog;

  // Insert a turn separator before this turn's entries
  const separator = { type: 'turn_separator', turn: turnNumber, message: `— Turn ${turnNumber} —` };
  const collapsedEntries = collapseLogEntries(newEntries);
  const combined = [...existingLog, separator, ...collapsedEntries];

  // Cap the log — keep the last LOG_MAX_ENTRIES entries
  if (combined.length > LOG_MAX_ENTRIES) {
    return combined.slice(combined.length - LOG_MAX_ENTRIES);
  }
  return combined;
}
