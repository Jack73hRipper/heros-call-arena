// ─────────────────────────────────────────────────────────────────────────────
// soundMap.js — Canonical mapping of sound keys to audio file paths
//
// This module provides helper functions for working with the audio-effects.json
// config. The actual key → file path mapping lives in audio-effects.json under
// the "_soundFiles" section, keeping it data-driven and editable without code
// changes (mirrors how particle-presets.json works for particles).
//
// Sound keys are short, descriptive identifiers used throughout the codebase:
//   'melee_hit', 'door_open', 'skill_heal', etc.
//
// File paths are relative to client/public/ (served by Vite at root):
//   '/audio/battle/swing.wav', '/audio/world/door.wav', etc.
//
// ─── Adding a new sound ─────────────────────────────────────────────────────
// 1. Place the .wav/.ogg/.mp3 file in client/public/audio/<category>/
// 2. Add a key → path entry to audio-effects.json → _soundFiles
// 3. Reference the key in the appropriate section (combat, skills, etc.)
// 4. The AudioManager will preload it automatically on init.
// ─────────────────────────────────────────────────────────────────────────────

/**
 * Sound categories — used for organizing the audio-effects.json file
 * and for documentation purposes.
 */
export const SOUND_CATEGORIES = {
  COMBAT: 'combat',       // Melee hits, ranged hits, death, damage taken
  SKILLS: 'skills',       // Per-skill sounds (heal, shield bash, etc.)
  ENVIRONMENT: 'environment', // Doors, chests, portal, floor transitions
  UI: 'ui',               // Button clicks, menu interactions
  AMBIENT: 'ambient',     // Looping background tracks (dungeon, town)
  EVENTS: 'events',       // Wave clear, floor descend, match start/end
};

/**
 * Sound keys — constants for all supported sound events.
 * Using constants prevents typos and enables IDE autocomplete.
 *
 * These keys correspond to entries in audio-effects.json.
 * Keys listed here may not all have sounds mapped yet — unmapped keys
 * simply produce no audio (silent fail by design).
 */
export const SOUND_KEYS = {
  // ── Combat ──
  MELEE_HIT: 'melee_hit',
  RANGED_HIT: 'ranged_hit',
  MISS: 'miss',
  DODGE: 'dodge',
  BLOCK: 'block',
  DEATH: 'death',
  SKILL_CAST: 'skill_cast',
  HEAL: 'heal',
  BUFF_APPLY: 'buff_apply',
  STUN_HIT: 'stun_hit',
  POTION_USE: 'potion_use',
  LOOT_PICKUP: 'loot_pickup',

  // ── Skills (per-skill overrides) ──
  SKILL_TAUNT: 'skill_taunt',
  SKILL_SHIELD_BASH: 'skill_shield_bash',
  SKILL_HOLY_GROUND: 'skill_holy_ground',
  SKILL_BULWARK: 'skill_bulwark',
  SKILL_POWER_SHOT: 'skill_power_shot',
  SKILL_VOLLEY: 'skill_volley',
  SKILL_EVASION: 'skill_evasion',
  SKILL_CRIPPLING_SHOT: 'skill_crippling_shot',
  SKILL_HEAL: 'skill_heal',
  SKILL_REBUKE: 'skill_rebuke',
  SKILL_EXORCISM: 'skill_exorcism',
  SKILL_PRAYER: 'skill_prayer',
  SKILL_SHIELD_OF_FAITH: 'skill_shield_of_faith',
  SKILL_DIVINE_SENSE: 'skill_divine_sense',
  SKILL_SHADOW_STEP: 'skill_shadow_step',
  SKILL_WITHER: 'skill_wither',
  SKILL_WARD: 'skill_ward',
  SKILL_SOUL_REAP: 'skill_soul_reap',
  SKILL_VENOM_GAZE: 'skill_venom_gaze',
  SKILL_WAR_CRY: 'skill_war_cry',
  SKILL_DOUBLE_STRIKE: 'skill_double_strike',
  SKILL_BALLAD_OF_MIGHT: 'skill_ballad_of_might',
  SKILL_DIRGE_OF_WEAKNESS: 'skill_dirge_of_weakness',
  SKILL_VERSE_OF_HASTE: 'skill_verse_of_haste',
  SKILL_CACOPHONY: 'skill_cacophony',
  SKILL_BLOOD_STRIKE: 'skill_blood_strike',
  SKILL_CRIMSON_VEIL: 'skill_crimson_veil',
  SKILL_SANGUINE_BURST: 'skill_sanguine_burst',
  SKILL_BLOOD_FRENZY: 'skill_blood_frenzy',
  SKILL_MIASMA: 'skill_miasma',
  SKILL_PLAGUE_FLASK: 'skill_plague_flask',
  SKILL_ENFEEBLE: 'skill_enfeeble',
  SKILL_INOCULATE: 'skill_inoculate',
  SKILL_GRAVE_THORNS: 'skill_grave_thorns',
  SKILL_GRAVE_CHAINS: 'skill_grave_chains',
  SKILL_UNDYING_WILL: 'skill_undying_will',
  SKILL_UNDYING_REVIVE: 'skill_undying_revive',
  SKILL_SOUL_REND: 'skill_soul_rend',
  SKILL_HEALING_TOTEM: 'skill_healing_totem',
  SKILL_SEARING_TOTEM: 'skill_searing_totem',
  SKILL_SOUL_ANCHOR: 'skill_soul_anchor',
  SKILL_SOUL_ANCHOR_SAVE: 'skill_soul_anchor_save',
  SKILL_EARTHGRASP: 'skill_earthgrasp',

  // ── Environment ──
  DOOR_OPEN: 'door_open',
  CHEST_OPEN: 'chest_open',
  PORTAL_CHANNEL: 'portal_channel',
  PORTAL_OPEN: 'portal_open',

  // ── Events ──
  WAVE_CLEAR: 'wave_clear',
  FLOOR_DESCEND: 'floor_descend',
  MATCH_START: 'match_start',
  MATCH_END: 'match_end',

  // ── Ambient ──
  AMBIENT_DUNGEON: 'ambient_dungeon',
  AMBIENT_TOWN: 'ambient_town',
  AMBIENT_ARENA: 'ambient_arena',

  // ── UI ──
  UI_CLICK: 'ui_click',
  UI_HOVER: 'ui_hover',
  UI_CONFIRM: 'ui_confirm',
  UI_CANCEL: 'ui_cancel',
  UI_EQUIP: 'ui_equip',
  UI_UNEQUIP: 'ui_unequip',
  UI_BUY: 'ui_buy',
  UI_SELL: 'ui_sell',
};

/**
 * Validate that all keys referenced in an effect map section
 * have corresponding entries in _soundFiles.
 *
 * @param {object} effectMap — The loaded audio-effects.json
 * @returns {{ valid: boolean, missing: string[] }}
 */
export function validateEffectMap(effectMap) {
  if (!effectMap || !effectMap._soundFiles) {
    return { valid: false, missing: ['_soundFiles section missing'] };
  }

  const soundFileKeys = new Set(Object.keys(effectMap._soundFiles));
  const missing = [];

  // Walk all sections and collect referenced keys
  for (const section of ['combat', 'skills', 'environment', 'events', 'ui']) {
    const entries = effectMap[section] || {};
    for (const [eventName, mapping] of Object.entries(entries)) {
      if (mapping.key && !soundFileKeys.has(mapping.key)) {
        missing.push(`${section}.${eventName} → "${mapping.key}"`);
      }
      if (mapping.variants) {
        for (const v of mapping.variants) {
          if (!soundFileKeys.has(v)) {
            missing.push(`${section}.${eventName}.variants → "${v}"`);
          }
        }
      }
    }
  }

  return { valid: missing.length === 0, missing };
}
