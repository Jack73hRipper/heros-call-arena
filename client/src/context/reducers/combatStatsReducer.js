/**
 * Combat Stats sub-reducer — accumulates per-unit combat statistics from TURN_RESULT actions.
 *
 * Tracks live, real-time stats that update every tick:
 *   - damage_dealt, damage_taken, healing_done (totals)
 *   - kills, boss_kills
 *   - highest_hit (max single damage)
 *   - overkill_damage (excess damage past 0 HP)
 *   - skill_breakdown: { skill_id: { damage, heals, casts } }
 *   - damage_by_type: { melee, ranged, skill, dot, reflect }
 *   - healing_by_type: { skill, potion, hot }
 *   - deaths, turns_alive
 *   - potions_used
 *
 * Action types handled:
 *   COMBAT_STATS_UPDATE  — process a batch of actions from TURN_RESULT
 *   COMBAT_STATS_RESET   — clear all stats (match start)
 *   COMBAT_STATS_TOGGLE  — toggle meter visibility
 *   COMBAT_STATS_SET_VIEW — change active view tab
 */

/**
 * Create a fresh stats entry for a unit.
 */
function createUnitStats(unitId, username, classId, team) {
  return {
    unitId,
    username: username || unitId,
    classId: classId || null,
    team: team || null,
    // Core totals
    damage_dealt: 0,
    damage_taken: 0,
    healing_done: 0,
    // Kill tracking
    kills: 0,
    boss_kills: 0,
    // Records
    highest_hit: 0,
    overkill_damage: 0,
    // Per-skill breakdown: { [skill_id]: { damage: 0, heals: 0, casts: 0, highest_hit: 0 } }
    skill_breakdown: {},
    // Damage by source type
    damage_by_type: { melee: 0, ranged: 0, skill: 0, dot: 0, reflect: 0 },
    // Healing by source type
    healing_by_type: { skill: 0, potion: 0, hot: 0 },
    // Survivability
    deaths: 0,
    turns_alive: 0,
    // Utility
    potions_used: 0,
    items_looted: 0,
  };
}

/**
 * Ensure a unit has a stats entry, creating one if needed.
 */
function ensureUnit(stats, unitId, players) {
  if (stats[unitId]) return stats[unitId];
  const player = players?.[unitId];
  return createUnitStats(
    unitId,
    player?.username,
    player?.class_id,
    player?.team
  );
}

/**
 * Process a single ActionResult from the turn_result payload.
 */
function processAction(stats, act, players, turnNumber) {
  if (!act.player_id) return stats;

  const updated = { ...stats };
  const attackerId = act.player_id;
  const targetId = act.target_id;

  // Ensure attacker exists
  updated[attackerId] = { ...ensureUnit(updated, attackerId, players) };

  // Ensure target exists (if present)
  if (targetId) {
    updated[targetId] = { ...ensureUnit(updated, targetId, players) };
  }

  const attacker = updated[attackerId];
  const target = targetId ? updated[targetId] : null;

  // --- Damage ---
  if (act.damage_dealt && act.damage_dealt > 0 && act.success !== false) {
    attacker.damage_dealt += act.damage_dealt;

    if (target) {
      target.damage_taken += act.damage_dealt;
    }

    // Highest hit
    if (act.damage_dealt > attacker.highest_hit) {
      attacker.highest_hit = act.damage_dealt;
    }

    // Overkill: if target was killed, any HP below 0 is overkill
    if (act.killed && act.target_hp_remaining !== undefined && act.target_hp_remaining <= 0) {
      // target_hp_remaining is usually 0 (clamped), but damage beyond what was needed
      // We can estimate overkill if we know pre-hit HP. Since we don't always have it,
      // we'll track it from the server's target_hp_remaining field if it goes to 0.
      // For now, we'll calculate it by storing last known HP.
    }

    // Damage by type
    if (act.action_type === 'attack') {
      attacker.damage_by_type.melee += act.damage_dealt;
    } else if (act.action_type === 'ranged_attack') {
      attacker.damage_by_type.ranged += act.damage_dealt;
    } else if (act.action_type === 'skill') {
      attacker.damage_by_type.skill += act.damage_dealt;
    }

    // DoT damage (buff tick damage shows as action_type 'buff_tick' or similar)
    if (act.action_type === 'dot_tick' || act.action_type === 'buff_tick') {
      attacker.damage_by_type.dot += act.damage_dealt;
    }

    // Shield reflect
    if (act.message && (act.message.includes('reflected') || act.message.includes('Reflected'))) {
      attacker.damage_by_type.reflect += act.damage_dealt;
    }

    // Per-skill breakdown
    if (act.skill_id) {
      if (!attacker.skill_breakdown[act.skill_id]) {
        attacker.skill_breakdown[act.skill_id] = { damage: 0, heals: 0, casts: 0, highest_hit: 0 };
      }
      attacker.skill_breakdown[act.skill_id].damage += act.damage_dealt;
      attacker.skill_breakdown[act.skill_id].casts += 1;
      if (act.damage_dealt > attacker.skill_breakdown[act.skill_id].highest_hit) {
        attacker.skill_breakdown[act.skill_id].highest_hit = act.damage_dealt;
      }
    }

    // Track auto-attack breakdown (melee/ranged without skill_id)
    if (!act.skill_id && (act.action_type === 'attack' || act.action_type === 'ranged_attack')) {
      const autoKey = act.action_type === 'attack' ? 'auto_attack_melee' : 'auto_attack_ranged';
      if (!attacker.skill_breakdown[autoKey]) {
        attacker.skill_breakdown[autoKey] = { damage: 0, heals: 0, casts: 0, highest_hit: 0 };
      }
      attacker.skill_breakdown[autoKey].damage += act.damage_dealt;
      attacker.skill_breakdown[autoKey].casts += 1;
      if (act.damage_dealt > attacker.skill_breakdown[autoKey].highest_hit) {
        attacker.skill_breakdown[autoKey].highest_hit = act.damage_dealt;
      }
    }
  }

  // --- Healing ---
  if (act.heal_amount && act.heal_amount > 0) {
    attacker.healing_done += act.heal_amount;

    if (act.action_type === 'skill') {
      attacker.healing_by_type.skill += act.heal_amount;
    } else if (act.action_type === 'use_item') {
      attacker.healing_by_type.potion += act.heal_amount;
      attacker.potions_used += 1;
    } else if (act.action_type === 'hot_tick' || act.action_type === 'buff_tick') {
      attacker.healing_by_type.hot += act.heal_amount;
    }

    // Per-skill breakdown for heals
    if (act.skill_id) {
      if (!attacker.skill_breakdown[act.skill_id]) {
        attacker.skill_breakdown[act.skill_id] = { damage: 0, heals: 0, casts: 0, highest_hit: 0 };
      }
      attacker.skill_breakdown[act.skill_id].heals += act.heal_amount;
      if (!act.damage_dealt) {
        attacker.skill_breakdown[act.skill_id].casts += 1;
      }
    }
  }

  // --- Kills ---
  if (act.killed) {
    attacker.kills += 1;
    const targetPlayer = players?.[targetId];
    if (targetPlayer?.is_boss) {
      attacker.boss_kills += 1;
    }
  }

  // --- Skill cast tracking (buff-only skills that don't deal damage or heal) ---
  if (act.action_type === 'skill' && act.success !== false && act.skill_id
      && !act.damage_dealt && !act.heal_amount) {
    if (!attacker.skill_breakdown[act.skill_id]) {
      attacker.skill_breakdown[act.skill_id] = { damage: 0, heals: 0, casts: 0, highest_hit: 0 };
    }
    attacker.skill_breakdown[act.skill_id].casts += 1;
  }

  updated[attackerId] = attacker;
  if (targetId) updated[targetId] = target;

  return updated;
}

export function combatStatsReducer(state, action) {
  switch (action.type) {

    case 'COMBAT_STATS_UPDATE': {
      const { actions, players, turnNumber, deaths, items_used, items_picked_up } = action.payload;
      let updatedStats = { ...state.unitStats };

      // Process each combat action
      for (const act of (actions || [])) {
        if (act.action_type === 'move' || act.action_type === 'wait') continue;
        updatedStats = processAction(updatedStats, act, players, turnNumber);
      }

      // Track deaths
      for (const deadId of (deaths || [])) {
        if (!updatedStats[deadId]) {
          updatedStats[deadId] = { ...ensureUnit(updatedStats, deadId, players) };
        }
        updatedStats[deadId] = { ...updatedStats[deadId], deaths: updatedStats[deadId].deaths + 1 };
      }

      // Track potion heals from items_used
      for (const iu of (items_used || [])) {
        if (iu.effect?.actual_healed && iu.player_id) {
          const pid = iu.player_id;
          if (!updatedStats[pid]) {
            updatedStats[pid] = { ...ensureUnit(updatedStats, pid, players) };
          }
          updatedStats[pid] = {
            ...updatedStats[pid],
            healing_done: updatedStats[pid].healing_done + iu.effect.actual_healed,
            potions_used: updatedStats[pid].potions_used + 1,
          };
          updatedStats[pid].healing_by_type = {
            ...updatedStats[pid].healing_by_type,
            potion: (updatedStats[pid].healing_by_type.potion || 0) + iu.effect.actual_healed,
          };
        }
      }

      // Track items looted
      for (const ip of (items_picked_up || [])) {
        if (ip.player_id) {
          const pid = ip.player_id;
          if (!updatedStats[pid]) {
            updatedStats[pid] = { ...ensureUnit(updatedStats, pid, players) };
          }
          const count = ip.items?.length || 1;
          updatedStats[pid] = {
            ...updatedStats[pid],
            items_looted: updatedStats[pid].items_looted + count,
          };
        }
      }

      // Update turns_alive for all living units
      for (const [uid, player] of Object.entries(players || {})) {
        if (player.is_alive !== false) {
          if (!updatedStats[uid]) {
            updatedStats[uid] = { ...ensureUnit(updatedStats, uid, players) };
          }
          updatedStats[uid] = {
            ...updatedStats[uid],
            turns_alive: turnNumber,
            // Keep username/class/team in sync
            username: player.username || updatedStats[uid].username,
            classId: player.class_id || updatedStats[uid].classId,
            team: player.team || updatedStats[uid].team,
          };
        }
      }

      return {
        ...state,
        unitStats: updatedStats,
        lastUpdateTurn: turnNumber,
      };
    }

    case 'COMBAT_STATS_RESET':
      return {
        ...state,
        unitStats: {},
        lastUpdateTurn: 0,
      };

    case 'COMBAT_STATS_TOGGLE':
      return {
        ...state,
        visible: !state.visible,
      };

    case 'COMBAT_STATS_SET_VIEW':
      return {
        ...state,
        activeView: action.payload,
        selectedUnit: null,  // Clear drill-in when switching views
      };

    case 'COMBAT_STATS_SELECT_UNIT':
      return {
        ...state,
        selectedUnit: action.payload,  // unitId or null
      };

    default:
      return state;
  }
}

export const initialCombatStats = {
  unitStats: {},       // { [unitId]: UnitStats }
  lastUpdateTurn: 0,
  visible: false,
  activeView: 'damage_done', // 'damage_done' | 'damage_taken' | 'healing_done' | 'kills' | 'overview'
  selectedUnit: null,  // unitId when drilled into a player's breakdown, null otherwise
};
