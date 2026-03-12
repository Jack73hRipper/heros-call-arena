/**
 * Combat sub-reducer — handles match lifecycle, turn resolution, queues, and combat log.
 *
 * Action types handled:
 *   UPDATE_PLAYERS, MATCH_START, TURN_RESULT, MATCH_END,
 *   WAVE_STARTED, CLEAR_FLOATERS, ADD_COMBAT_LOG, PLAYER_STATS_UPDATED,
 *   QUEUE_ACTION, QUEUE_UPDATED, QUEUE_CLEARED, GROUP_BATCH_QUEUED,
 *   CLEAR_ACTION, SET_ACTION_MODE
 *
 * Log building is delegated to combatLogBuilder.js (Phase CL: Combat Log Overhaul).
 */

import { buildTurnLogEntries, appendAndCapLog, LOG_MAX_ENTRIES } from '../../utils/combatLogBuilder';

export function combatReducer(state, action) {
  switch (action.type) {
    case 'UPDATE_PLAYERS':
      return { ...state, players: action.payload };

    case 'MATCH_START': {
      // Build initial FOV set from visible_tiles if provided
      let initialFov = null;
      let initialRevealed = null;
      if (action.payload.visible_tiles && action.payload.visible_tiles.length > 0) {
        initialFov = new Set(action.payload.visible_tiles.map(([x, y]) => `${x},${y}`));
        initialRevealed = new Set(initialFov);
      }
      return {
        ...state,
        matchStatus: 'in_progress',
        players: action.payload.players,
        gridWidth: action.payload.grid_width || 15,
        gridHeight: action.payload.grid_height || 15,
        obstacles: action.payload.obstacles || [],
        tickRate: action.payload.tick_rate || 10,
        matchType: action.payload.match_type || 'pvp',
        isPvpve: action.payload.match_type === 'pvpve',
        teamA: action.payload.team_a || [],
        teamB: action.payload.team_b || [],
        teamC: action.payload.team_c || [],
        teamD: action.payload.team_d || [],
        aiIds: action.payload.ai_ids || [],
        // Dungeon data (4B-2)
        isDungeon: !!action.payload.is_dungeon,
        tiles: action.payload.tiles || null,
        tileLegend: action.payload.tile_legend || null,
        doorStates: action.payload.door_states || {},
        chestStates: action.payload.chest_states || {},
        themeId: action.payload.theme_id || null,
        // Phase 27E: Boss room metadata for minimap
        bossRoom: action.payload.boss_room || null,
        // Initial FOV from server (prevents full-map flash)
        visibleTiles: initialFov,
        revealedTiles: initialRevealed,
        // Reset loot state on match start
        inventory: [],
        equipment: { weapon: null, armor: null, accessory: null },
        groundItems: {},
        // Phase 19: Track starting gold for "earned this run" display
        startGold: state.gold,
        // Reset party control state
        activeUnitId: null,
        selectedUnitIds: [],
        partyMembers: [],
        partyQueues: {},
        partyInventories: {},
        // Reset auto-target state
        autoTargetId: null,
        partyAutoTargets: {},
        autoSkillId: null,
        partyAutoSkills: {},
        selectedTargetId: null,
        // Phase 12C: Reset portal state
        portal: null,
        channeling: null,
        // Phase 26E: Reset totems
        totems: [],
        // Phase 23: Reset ground zones
        groundZones: [],
        // Phase 12-5: Floor tracking
        currentFloor: action.payload.current_floor || 1,
        stairsUnlocked: action.payload.stairs_unlocked || false,
        // Phase 6C: Extract class skills for skill bar
        classSkills: (() => {
          const myClassId = action.payload.players?.[state.playerId]?.class_id;
          return (action.payload.class_skills?.[myClassId]) || [];
        })(),
        allClassSkills: action.payload.class_skills || {},
        currentTurn: 0,
        combatLog: [{ message: 'Match started!', type: 'system' }],
      };
    }

    case 'TURN_RESULT': {
      const { turn_number, actions, deaths, winner, players: updatedPlayers, visible_tiles,
              door_changes, door_states: newDoorStates, chest_states: newChestStates,
              my_inventory, my_equipment, ground_items: newGroundItems,
              loot_drops, chest_opened, items_picked_up, items_used } = action.payload;

      // Build FOV set from visible_tiles array
      let fovSet = null;
      if (visible_tiles && visible_tiles.length > 0) {
        fovSet = new Set(visible_tiles.map(([x, y]) => `${x},${y}`));
      }

      // Accumulate revealed tiles (roguelike exploration)
      let updatedRevealed = state.revealedTiles;
      if (fovSet) {
        updatedRevealed = new Set(state.revealedTiles || []);
        for (const tile of fovSet) {
          updatedRevealed.add(tile);
        }
      }

      // Update door states from server if provided
      let updatedDoorStates = state.doorStates;
      if (newDoorStates) {
        updatedDoorStates = newDoorStates;
      } else if (door_changes && door_changes.length > 0) {
        updatedDoorStates = { ...state.doorStates };
        for (const dc of door_changes) {
          updatedDoorStates[`${dc.x},${dc.y}`] = dc.state;
        }
      }

      let updatedChestStates = newChestStates || state.chestStates;

      // Update inventory/equipment from server private state
      const updatedInventory = my_inventory ?? state.inventory;
      const updatedEquipment = my_equipment ?? state.equipment;
      const updatedGroundItems = newGroundItems ?? state.groundItems;

      // Phase CL: Delegate log + floater building to extracted utility
      const { logEntries, floaters: newFloaters } = buildTurnLogEntries(
        action.payload, state, updatedPlayers
      );

      const eliteKills = action.payload.elite_kills;
      // Phase 27E: Team elimination events for PVPVE
      const teamEliminations = action.payload.team_eliminations || [];

      // Phase 12C: Auto-release control when active unit gets extracted
      // If the currently controlled unit just extracted, switch to next available hero
      let newActiveUnitId = state.activeUnitId;
      let newSelectedUnitIds = state.selectedUnitIds;
      const effectiveActive = state.activeUnitId || state.playerId;
      const effectivePlayer = (updatedPlayers || state.players)[effectiveActive];
      if (effectivePlayer && effectivePlayer.extracted) {
        // Find next alive, non-extracted party member (or player itself)
        const candidates = [state.playerId, ...(state.partyMembers || []).map(m => m.unit_id)];
        const nextUnit = candidates.find(uid => {
          const u = (updatedPlayers || state.players)[uid];
          return u && u.is_alive !== false && !u.extracted && uid !== effectiveActive;
        });
        newActiveUnitId = nextUnit || null;
        newSelectedUnitIds = nextUnit ? [nextUnit] : [];
      }

      // Phase 23: Ground zone tracking (Miasma persistent clouds, Enfeeble zones)
      // Decrement existing zones, add new ones from this turn's actions, remove expired
      const GROUND_ZONE_SKILLS = {
        miasma:  { radius: 2, color: '#50C878', duration: 2 },
        enfeeble: { radius: 2, color: '#8844aa', duration: 3 },
      };
      let updatedGroundZones = (state.groundZones || [])
        .map(z => ({ ...z, turnsRemaining: z.turnsRemaining - 1 }))
        .filter(z => z.turnsRemaining > 0);
      if (actions && actions.length > 0) {
        for (const act of actions) {
          if (act.skill_id && GROUND_ZONE_SKILLS[act.skill_id] && act.success && act.to_x != null && act.to_y != null) {
            const cfg = GROUND_ZONE_SKILLS[act.skill_id];
            // Remove any existing zone at the same position from the same skill (refresh)
            updatedGroundZones = updatedGroundZones.filter(
              z => !(z.skillId === act.skill_id && z.x === act.to_x && z.y === act.to_y)
            );
            updatedGroundZones.push({
              id: `${act.skill_id}_${act.to_x}_${act.to_y}_${turn_number}`,
              x: act.to_x,
              y: act.to_y,
              radius: cfg.radius,
              turnsRemaining: cfg.duration,
              color: cfg.color,
              skillId: act.skill_id,
            });
          }
        }
      }

      return {
        ...state,
        players: updatedPlayers || state.players,
        currentTurn: turn_number,
        visibleTiles: fovSet,
        revealedTiles: updatedRevealed,
        queuedAction: null,
        combatLog: appendAndCapLog(state.combatLog, logEntries, turn_number),
        winner: winner || state.winner,
        damageFloaters: [...state.damageFloaters, ...newFloaters],
        doorStates: updatedDoorStates,
        chestStates: updatedChestStates,
        inventory: updatedInventory,
        equipment: updatedEquipment,
        groundItems: updatedGroundItems,
        // Phase 12C: Portal state from server
        portal: action.payload.portal || null,
        channeling: action.payload.channeling || null,
        // Phase 26E: Totem entities from server
        totems: action.payload.totems || [],
        // Phase 23: Persistent AoE ground zones
        groundZones: updatedGroundZones,
        // Phase 12-5: Stairs unlock state
        stairsUnlocked: action.payload.stairs_unlocked ?? state.stairsUnlocked,
        currentFloor: action.payload.current_floor ?? state.currentFloor,
        partyInventories: action.payload.party_inventories
          ? { ...state.partyInventories, ...action.payload.party_inventories }
          : state.partyInventories,
        lastTurnActions: {
          actions: actions || [],
          doorChanges: door_changes || [],
          chestOpened: chest_opened || [],
        },
        ...(action.payload.auto_targets != null ? {
          autoTargetId: (() => {
            const entry = action.payload.auto_targets[state.playerId];
            return entry ? (entry.target_id || entry) : null;
          })(),
          autoSkillId: (() => {
            const entry = action.payload.auto_targets[state.playerId];
            return entry ? (entry.skill_id || null) : null;
          })(),
          partyAutoTargets: (() => {
            const pat = {};
            for (const [uid, entry] of Object.entries(action.payload.auto_targets)) {
              if (uid !== state.playerId) pat[uid] = entry.target_id || entry;
            }
            return pat;
          })(),
          partyAutoSkills: (() => {
            const pas = {};
            for (const [uid, entry] of Object.entries(action.payload.auto_targets)) {
              if (uid !== state.playerId && entry.skill_id) pas[uid] = entry.skill_id;
            }
            return pas;
          })(),
        } : {}),
        // ^^ When server omits auto_targets (empty dict), preserve existing
        // client-side auto-target state. Previously this wiped to null,
        // causing auto-attack to stop after spell casts.
        // Phase 12C: Auto-switch control away from extracted units
        activeUnitId: newActiveUnitId,
        selectedUnitIds: newSelectedUnitIds,
        // Phase 18F: Elite kills for notification display
        eliteKills: eliteKills || [],
        // Phase 27E: Team eliminations for PVPVE notifications
        teamEliminations: teamEliminations,
      };
    }

    case 'FLOOR_ADVANCE': {
      // Phase 12-5: Party descended to next floor — full map reset
      const fa = action.payload;
      let newFov = null;
      let newRevealed = null;
      if (fa.visible_tiles && fa.visible_tiles.length > 0) {
        newFov = new Set(fa.visible_tiles.map(([x, y]) => `${x},${y}`));
        newRevealed = new Set(newFov);
      }
      return {
        ...state,
        players: fa.players || state.players,
        gridWidth: fa.grid_width || state.gridWidth,
        gridHeight: fa.grid_height || state.gridHeight,
        obstacles: fa.obstacles || state.obstacles,
        tiles: fa.tiles || null,
        tileLegend: fa.tile_legend || null,
        doorStates: fa.door_states || {},
        chestStates: fa.chest_states || {},
        groundItems: {},
        isDungeon: true,
        themeId: fa.theme_id || state.themeId,
        currentFloor: fa.floor_number || state.currentFloor + 1,
        stairsUnlocked: fa.stairs_unlocked || false,
        visibleTiles: newFov,
        revealedTiles: newRevealed,
        // Reset portal/channeling/ground zones on floor change
        portal: null,
        channeling: null,
        groundZones: [],
        // Reset auto-targets
        autoTargetId: null,
        partyAutoTargets: {},
        autoSkillId: null,
        partyAutoSkills: {},
        selectedTargetId: null,
        damageFloaters: [],
        combatLog: appendAndCapLog(state.combatLog, [
          { message: `Descended to Floor ${fa.floor_number}`, type: 'system' },
        ], `F${fa.floor_number}`),
      };
    }

    case 'QUEUE_ACTION':
      return { ...state, queuedAction: action.payload };

    case 'QUEUE_UPDATED': {
      const queueUnitId = action.payload.unit_id;
      const queueData = action.payload.queue || [];
      if (queueUnitId && queueUnitId !== state.playerId) {
        return {
          ...state,
          partyQueues: { ...state.partyQueues, [queueUnitId]: queueData },
          partyMembers: action.payload.party || state.partyMembers,
        };
      }
      return {
        ...state,
        actionQueue: queueData,
        queuedAction: queueData.length > 0 ? queueData[queueData.length - 1] : null,
        partyMembers: action.payload.party || state.partyMembers,
      };
    }

    case 'QUEUE_CLEARED': {
      const clearedUnitId = action.payload.unit_id;
      if (clearedUnitId && clearedUnitId !== state.playerId) {
        return {
          ...state,
          partyQueues: { ...state.partyQueues, [clearedUnitId]: [] },
        };
      }
      return {
        ...state,
        actionQueue: [],
        queuedAction: null,
        actionMode: null,
      };
    }

    case 'GROUP_BATCH_QUEUED': {
      const { queues, queued, failed } = action.payload;
      const newPartyQueues = { ...state.partyQueues };
      let newActionQueue = state.actionQueue;

      if (queues) {
        for (const [unitId, queueData] of Object.entries(queues)) {
          if (unitId === state.playerId) {
            newActionQueue = queueData;
          } else {
            newPartyQueues[unitId] = queueData;
          }
        }
      }

      return {
        ...state,
        actionQueue: newActionQueue,
        partyQueues: newPartyQueues,
        queuedAction: newActionQueue.length > 0 ? newActionQueue[newActionQueue.length - 1] : null,
      };
    }

    case 'CLEAR_ACTION':
      return { ...state, queuedAction: null, actionMode: null };

    case 'SET_ACTION_MODE':
      return { ...state, actionMode: action.payload, selectedTargetId: action.payload ? null : state.selectedTargetId };

    case 'ADD_COMBAT_LOG': {
      const newLog = [...state.combatLog, action.payload];
      return {
        ...state,
        combatLog: newLog.length > LOG_MAX_ENTRIES ? newLog.slice(newLog.length - LOG_MAX_ENTRIES) : newLog,
      };
    }

    case 'CLEAR_FLOATERS':
      return {
        ...state,
        damageFloaters: state.damageFloaters.filter(
          f => Date.now() - f.createdAt < 1500
        ),
      };

    case 'PLAYER_STATS_UPDATED': {
      const { player_id: statsPid, stats } = action.payload;
      if (!statsPid || !state.players[statsPid]) return state;
      return {
        ...state,
        players: {
          ...state.players,
          [statsPid]: { ...state.players[statsPid], ...stats },
        },
      };
    }

    case 'WAVE_STARTED': {
      const { wave_number, wave_name, enemy_count, total_waves } = action.payload;
      return {
        ...state,
        waveNumber: wave_number,
        totalWaves: total_waves,
        combatLog: appendAndCapLog(state.combatLog, [
          {
            message: `Wave ${wave_number}/${total_waves}: ${wave_name} — ${enemy_count} enemies incoming!`,
            type: 'wave',
          },
        ], `W${wave_number}`),
      };
    }

    case 'MATCH_END': {
      const winMsg = action.payload.winner === 'dungeon_extract'
        ? 'Dungeon cleared! Your party escaped through the portal!'
        : action.payload.winner === 'party_wipe'
        ? 'Party wiped! All heroes have fallen...'
        : `Match over! ${action.payload.winner_username} wins!`;
      return {
        ...state,
        matchStatus: 'finished',
        winner: action.payload.winner,
        winnerUsername: action.payload.winner_username,
        heroOutcomes: action.payload.hero_outcomes || null,
        portal: null,
        channeling: null,
        combatLog: appendAndCapLog(state.combatLog, [
          { message: winMsg, type: action.payload.winner === 'party_wipe' ? 'death' : 'kill' },
        ], 'End'),
      };
    }

    default:
      return state;
  }
}
