// ─────────────────────────────────────────────────────────
// moduleLibrary.js — Canonical JSON module library format
//
// Shared format between the WFC Dungeon Tool (JS) and the
// game server (Python).  Single source of truth for modules.
//
// Version 2 format:
//   { version: 2, module_size: 8, modules: [...], size_presets: [...] }
// ─────────────────────────────────────────────────────────

import { MODULE_SIZE } from '../engine/moduleUtils.js';
import { SIZE_PRESETS } from '../engine/presets.js';

/** Current library format version */
export const MODULE_LIBRARY_VERSION = 2;

/** Required fields on every module */
const REQUIRED_FIELDS = [
  'id', 'name', 'purpose', 'contentRole',
  'width', 'height', 'weight', 'allowRotation',
  'spawnSlots', 'maxEnemies', 'maxChests',
  'canBeBoss', 'canBeSpawn', 'tiles',
];

/**
 * Export the current module library to the canonical JSON format.
 *
 * @param {Array} modules - Array of module objects from the tool
 * @returns {Object} Library JSON object ready for serialization
 */
export function exportModuleLibrary(modules) {
  if (!Array.isArray(modules) || modules.length === 0) {
    throw new Error('No modules to export');
  }

  // Clean each module to only include canonical fields
  const cleanModules = modules.map(mod => {
    const clean = {};
    for (const field of REQUIRED_FIELDS) {
      if (mod[field] !== undefined) {
        clean[field] = mod[field];
      } else {
        // Apply sensible defaults for missing fields
        switch (field) {
          case 'contentRole': clean[field] = 'structural'; break;
          case 'spawnSlots': clean[field] = []; break;
          case 'maxEnemies': clean[field] = 0; break;
          case 'maxChests': clean[field] = 0; break;
          case 'canBeBoss': clean[field] = false; break;
          case 'canBeSpawn': clean[field] = false; break;
          default:
            throw new Error(`Module "${mod.id || mod.name}" missing required field: ${field}`);
        }
      }
    }
    return clean;
  });

  return {
    version: MODULE_LIBRARY_VERSION,
    module_size: MODULE_SIZE,
    generated_from: 'tools/dungeon-wfc',
    modules: cleanModules,
    size_presets: SIZE_PRESETS,
  };
}

/**
 * Import a canonical JSON library and return an array of modules.
 *
 * @param {Object} json - Parsed library JSON
 * @returns {Array} Array of module objects suitable for the tool
 * @throws {Error} If the JSON is invalid or incompatible
 */
export function importModuleLibrary(json) {
  if (!json || typeof json !== 'object') {
    throw new Error('Invalid library JSON');
  }

  const version = json.version || 1;
  if (version < 2) {
    throw new Error(`Unsupported library version ${version} (need >= 2)`);
  }

  const modules = json.modules;
  if (!Array.isArray(modules) || modules.length === 0) {
    throw new Error('Library has no modules');
  }

  // Validate each module has required fields
  const valid = [];
  const warnings = [];
  for (const mod of modules) {
    const missing = REQUIRED_FIELDS.filter(f => mod[f] === undefined);
    if (missing.length > 0) {
      warnings.push(`Module "${mod.id || '?'}" missing: ${missing.join(', ')}`);
      continue;
    }
    valid.push(mod);
  }

  if (warnings.length > 0) {
    console.warn('[moduleLibrary] Import warnings:', warnings);
  }

  if (valid.length === 0) {
    throw new Error('No valid modules in library');
  }

  console.log(`[moduleLibrary] Imported ${valid.length} modules (v${version})`);
  return valid;
}

/**
 * Fetch the canonical module library from the game server.
 *
 * @param {string} [url='/api/maps/wfc-modules/library'] - Server endpoint
 * @returns {Promise<Array|null>} Array of modules, or null if not available
 */
export async function fetchServerLibrary(url = '/api/maps/wfc-modules/library') {
  try {
    const res = await fetch(url);
    if (!res.ok) return null;
    const json = await res.json();
    return importModuleLibrary(json);
  } catch (err) {
    console.warn('[moduleLibrary] Could not fetch server library:', err.message);
    return null;
  }
}
