import React, { createContext, useContext, useReducer, useCallback } from 'react';
import { lobbyReducer } from './reducers/lobbyReducer';
import { combatReducer } from './reducers/combatReducer';
import { partyReducer } from './reducers/partyReducer';
import { townReducer } from './reducers/townReducer';
import { inventoryReducer } from './reducers/inventoryReducer';
import { combatStatsReducer, initialCombatStats } from './reducers/combatStatsReducer';

const GameStateContext = createContext(null);
const GameDispatchContext = createContext(null);
const CombatStatsContext = createContext(null);
const CombatStatsDispatchContext = createContext(null);

export const initialState = {
  // Player identity
  username: '',
  playerId: null,

  // Match info
  matchId: null,
  matchStatus: null, // 'waiting' | 'in_progress' | 'finished'

  // Lobby state
  lobbyPlayers: {},  // { playerId: { username, position, hp, max_hp, is_ready, ... } }
  lobbyChat: [],     // [{ sender, sender_id, message, timestamp }, ...]
  lobbyConfig: null, // { map_id, match_type, ai_opponents, ai_allies, max_players, host_id }

  // Game state (updated each turn)
  players: {},       // { playerId: { username, position, hp, isAlive, unit_type, team, ... } }
  currentTurn: 0,
  gridWidth: 15,
  gridHeight: 15,
  obstacles: [],
  tickRate: 10,

  // Phase 2: FOV — set of visible tile coords from server
  visibleTiles: null, // Set of "x,y" strings, null means show everything (pre-FOV)
  revealedTiles: null, // Set of "x,y" strings — tiles ever seen (for roguelike exploration fog)

  // Phase 2: Teams and AI
  matchType: 'pvp',   // 'pvp' | 'solo_pve' | 'mixed'
  teamA: [],          // unit IDs on team A
  teamB: [],          // unit IDs on team B
  teamC: [],          // unit IDs on team C
  teamD: [],          // unit IDs on team D
  aiIds: [],          // all AI unit IDs

  // Phase 4A: Class system
  availableClasses: null,  // fetched from server: { class_id: { name, role, ... } }

  // Phase 4B: Dungeon state
  isDungeon: false,
  tiles: null,           // 2D array of tile characters (dungeon maps only)
  tileLegend: null,      // { "W": "wall", "F": "floor", ... }
  doorStates: {},        // { "x,y": "open"/"closed" }
  chestStates: {},       // { "x,y": "unopened"/"opened" }

  // Phase 4D: Inventory & Loot
  inventory: [],           // list of item dicts in player's bag (max 10)
  equipment: { weapon: null, armor: null, accessory: null }, // equipped items
  groundItems: {},         // { "x,y": [item, ...] } — loot on the ground

  // Phase 4E: Town Hub & Heroes
  gold: 0,                   // Player's gold from profile
  startGold: 0,              // Gold at match start (for tracking earnings)
  heroes: [],                // Owned hero roster [{hero_id, name, class_id, stats, ...}]
  tavernHeroes: [],           // Available heroes for hire from tavern
  selectedHeroIds: [],         // Heroes selected for current dungeon run (max 4)
  heroDeaths: [],             // [{hero_id, hero_name, class_id, lost_items}] from last match
  heroOutcomes: null,         // Per-player outcomes from match_end
  postMatchSummary: null,     // Summary data for post-match screen
  lobbyError: null,            // Error message from server (displayed in lobby)
  bank: [],                    // Account-wide bank storage (max 20 items)

  // Phase 12C: Portal Scroll state
  portal: null,        // { active, x, y, turns_remaining, owner_id } or null
  channeling: null,    // { player_id, action, turns_remaining, tile_x, tile_y } or null

  // Phase 26E: Shaman totem entities
  totems: [],          // [{ id, type, owner_id, x, y, hp, max_hp, effect_radius, duration_remaining, team, ... }]

  // Persistent action queue (from server, up to 10)
  actionQueue: [],   // [{ action_type, target_x, target_y, skill_id }, ...]

  // Legacy single queued action (kept for backward compat)
  queuedAction: null,

  // Action mode for UI
  actionMode: null, // 'move' | 'attack' | 'ranged_attack' | 'skill_<skill_id>' | null

  // Phase 5: Party control
  activeUnitId: null,    // Currently controlled unit (null = self). Set to a party member's unit_id to control them
  selectedUnitIds: [],   // Phase 7B-2: All selected unit IDs (multi-select). activeUnitId is the "primary" from this set
  partyMembers: [],      // [{unit_id, username, class_id, hp, max_hp, is_alive, hero_id, controlled_by, position, ai_stance}]
  partyQueues: {},       // {unit_id: [{action_type, target_x, target_y, skill_id}, ...]} — per-unit action queues
  partyInventories: {},  // {unit_id: {inventory: [], equipment: {}}} — party member inventories (dungeon)

  // Phase 10C: Auto-target pursuit state
  autoTargetId: null,      // Current player's auto-target enemy ID
  partyAutoTargets: {},    // { unitId: targetId } for party members
  // Phase 10G: Skill auto-target + selected target state
  autoSkillId: null,       // Skill being auto-cast alongside autoTargetId
  partyAutoSkills: {},     // { unitId: skillId } for party members
  selectedTargetId: null,  // Unit currently soft-selected via left-click (client-only)

  // Phase 6C: Skills state
  classSkills: [],        // Array of skill definitions for my class
  allClassSkills: {},     // Map of class_id -> skill defs (for party members)

  // Combat log
  combatLog: [],

  // Match end info
  winner: null,
  winnerUsername: '',

  // Damage floaters for visual feedback
  damageFloaters: [], // [{ id, x, y, text, color, createdAt }, ...]

  // Phase 9E: Raw turn actions for particle effects (consumed by ParticleManager)
  lastTurnActions: null, // { actions, doorChanges, chestOpened }

  // Phase 23: Persistent AoE ground zones (Miasma clouds, etc.)
  groundZones: [], // [{ id, x, y, radius, turnsRemaining, color, skillId }, ...]
};

// Action type → sub-reducer dispatch table
const LOBBY_ACTIONS = new Set([
  'SET_USERNAME', 'JOIN_MATCH', 'PLAYER_JOINED', 'PLAYER_READY',
  'PLAYER_DISCONNECTED', 'TEAM_CHANGED', 'CLASS_CHANGED',
  'SET_AVAILABLE_CLASSES', 'CHAT_MESSAGE', 'CONFIG_CHANGED',
  'SET_LOBBY_ERROR', 'HERO_SELECTED',
]);

const COMBAT_ACTIONS = new Set([
  'UPDATE_PLAYERS', 'MATCH_START', 'TURN_RESULT', 'MATCH_END',
  'WAVE_STARTED', 'FLOOR_ADVANCE', 'CLEAR_FLOATERS', 'ADD_COMBAT_LOG', 'PLAYER_STATS_UPDATED',
  'QUEUE_ACTION', 'QUEUE_UPDATED', 'QUEUE_CLEARED', 'GROUP_BATCH_QUEUED',
  'CLEAR_ACTION', 'SET_ACTION_MODE',
]);

const PARTY_ACTIONS = new Set([
  'SELECT_ACTIVE_UNIT', 'TOGGLE_UNIT_SELECTION', 'SELECT_ALL_PARTY',
  'DESELECT_ALL_UNITS', 'PARTY_MEMBER_SELECTED', 'PARTY_MEMBER_RELEASED',
  'STANCE_UPDATED', 'ALL_STANCES_UPDATED',
  'AUTO_TARGET_SET', 'AUTO_TARGET_CLEARED', 'CLEAR_AUTO_TARGET',
  'SELECT_TARGET', 'CLEAR_SELECTED_TARGET',
]);

const TOWN_ACTIONS = new Set([
  'SET_PROFILE', 'SET_TAVERN', 'HIRE_HERO', 'SELECT_HERO',
  'HERO_DIED', 'SET_POST_MATCH_SUMMARY', 'CLEAR_POST_MATCH',
  'MERCHANT_BUY', 'MERCHANT_SELL',
  'HERO_EQUIP', 'HERO_UNEQUIP', 'HERO_TRANSFER',
  'BANK_DEPOSIT', 'BANK_WITHDRAW',
  'DISMISS_HERO',
  'LEAVE_MATCH',
]);

const INVENTORY_ACTIONS = new Set([
  'ITEM_EQUIPPED', 'ITEM_UNEQUIPPED', 'ITEM_TRANSFERRED', 'PARTY_INVENTORY',
]);

function gameReducer(state, action) {
  const { type } = action;
  if (LOBBY_ACTIONS.has(type)) return lobbyReducer(state, action);
  if (COMBAT_ACTIONS.has(type)) return combatReducer(state, action);
  if (PARTY_ACTIONS.has(type)) return partyReducer(state, action);
  if (TOWN_ACTIONS.has(type)) return townReducer(state, action);
  if (INVENTORY_ACTIONS.has(type)) return inventoryReducer(state, action);
  return state;
}

export function GameStateProvider({ children }) {
  const [state, dispatch] = useReducer(gameReducer, initialState);
  const [combatStats, combatStatsDispatch] = useReducer(combatStatsReducer, initialCombatStats);

  // Combined dispatch: routes combat stats actions to their reducer,
  // and also mirrors TURN_RESULT / MATCH_START to the stats reducer
  const combinedDispatch = useCallback((action) => {
    dispatch(action);

    // Combat stats actions go to their own reducer
    if (action.type === 'COMBAT_STATS_TOGGLE' ||
        action.type === 'COMBAT_STATS_SET_VIEW' ||
        action.type === 'COMBAT_STATS_RESET' ||
        action.type === 'COMBAT_STATS_UPDATE') {
      combatStatsDispatch(action);
    }

    // Reset stats on match start
    if (action.type === 'MATCH_START') {
      combatStatsDispatch({ type: 'COMBAT_STATS_RESET' });
    }
  }, [dispatch, combatStatsDispatch]);

  return (
    <GameStateContext.Provider value={state}>
      <GameDispatchContext.Provider value={combinedDispatch}>
        <CombatStatsContext.Provider value={combatStats}>
          <CombatStatsDispatchContext.Provider value={combatStatsDispatch}>
            {children}
          </CombatStatsDispatchContext.Provider>
        </CombatStatsContext.Provider>
      </GameDispatchContext.Provider>
    </GameStateContext.Provider>
  );
}

export function useGameState() {
  return useContext(GameStateContext);
}

export function useGameDispatch() {
  return useContext(GameDispatchContext);
}

export function useCombatStats() {
  return useContext(CombatStatsContext);
}

export function useCombatStatsDispatch() {
  return useContext(CombatStatsDispatchContext);
}
