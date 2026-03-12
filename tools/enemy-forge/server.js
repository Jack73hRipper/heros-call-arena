// ─────────────────────────────────────────────────────────
// server.js — Micro API for Enemy Forge (config file I/O)
// ─────────────────────────────────────────────────────────
// Provides read/write access to all enemy-related JSON configs:
//   - enemies_config.json
//   - monster_rarity_config.json
//   - skills_config.json
//   - classes_config.json
//   - combat_config.json
//   - loot_tables.json
//   - names_config.json
//
// Also reads the floor enemy roster from dungeon_generator.py

import express from 'express';
import cors from 'cors';
import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const app = express();
const PORT = 5231;

// Paths relative to project root
const PROJECT_ROOT = path.resolve(__dirname, '../..');
const CONFIGS_DIR = path.join(PROJECT_ROOT, 'server', 'configs');
const DUNGEON_GEN_PATH = path.join(PROJECT_ROOT, 'server', 'app', 'core', 'wfc', 'dungeon_generator.py');

// Config file registry — each key maps to a JSON file
const CONFIG_FILES = {
  enemies:        path.join(CONFIGS_DIR, 'enemies_config.json'),
  rarity:         path.join(CONFIGS_DIR, 'monster_rarity_config.json'),
  skills:         path.join(CONFIGS_DIR, 'skills_config.json'),
  classes:        path.join(CONFIGS_DIR, 'classes_config.json'),
  combat:         path.join(CONFIGS_DIR, 'combat_config.json'),
  loot_tables:    path.join(CONFIGS_DIR, 'loot_tables.json'),
  names:          path.join(CONFIGS_DIR, 'names_config.json'),
  super_uniques:  path.join(CONFIGS_DIR, 'super_uniques_config.json'),
};

// Sprite atlas & sheet paths
const SPRITE_ATLAS_PATH = path.join(PROJECT_ROOT, 'Assets', 'Sprites', 'Combined Character Sheet 1-atlas (3).json');
const SPRITE_SHEET_PATH = path.join(PROJECT_ROOT, 'client', 'public', 'spritesheet.png');

app.use(cors());
app.use(express.json({ limit: '10mb' }));

// ── Helper: read a config file ────────────────────────
function readConfig(key) {
  const filePath = CONFIG_FILES[key];
  if (!filePath) throw new Error(`Unknown config key: ${key}`);
  if (!fs.existsSync(filePath)) return null;
  const raw = fs.readFileSync(filePath, 'utf-8');
  return JSON.parse(raw);
}

// ── Helper: write a config file with backup ───────────
function writeConfig(key, data) {
  const filePath = CONFIG_FILES[key];
  if (!filePath) throw new Error(`Unknown config key: ${key}`);

  // Create backup before overwriting
  if (fs.existsSync(filePath)) {
    const baseName = path.basename(filePath, '.json');
    const backupPath = path.join(
      path.dirname(filePath),
      `${baseName}.backup-${Date.now()}.json`
    );
    fs.copyFileSync(filePath, backupPath);

    // Clean old backups — keep only last 5 per config
    const dir = path.dirname(filePath);
    const prefix = `${baseName}.backup-`;
    const backups = fs.readdirSync(dir)
      .filter(f => f.startsWith(prefix) && f.endsWith('.json'))
      .sort()
      .reverse();
    backups.slice(5).forEach(f => fs.unlinkSync(path.join(dir, f)));
  }

  const json = JSON.stringify(data, null, 2);
  fs.writeFileSync(filePath, json, 'utf-8');
}

// ── GET /api/configs — read ALL config files at once ──
app.get('/api/configs', (_req, res) => {
  try {
    const result = {};
    for (const key of Object.keys(CONFIG_FILES)) {
      try {
        result[key] = readConfig(key);
      } catch {
        result[key] = null;
      }
    }
    res.json(result);
  } catch (err) {
    res.status(500).json({ error: `Failed to read configs: ${err.message}` });
  }
});

// ── GET /api/config/:key — read a single config file ──
app.get('/api/config/:key', (req, res) => {
  try {
    const data = readConfig(req.params.key);
    if (data === null) {
      return res.status(404).json({ error: `Config file not found: ${req.params.key}` });
    }
    res.json(data);
  } catch (err) {
    res.status(500).json({ error: `Failed to read config: ${err.message}` });
  }
});

// ── POST /api/config/:key — write a single config file ─
app.post('/api/config/:key', (req, res) => {
  try {
    writeConfig(req.params.key, req.body);
    res.json({ success: true, key: req.params.key });
  } catch (err) {
    res.status(500).json({ error: `Failed to write config: ${err.message}` });
  }
});

// ── POST /api/config/:key/entry — add or update a single entry ─
app.post('/api/config/:key/entry', (req, res) => {
  try {
    const { entryKey, entryData, section } = req.body;
    if (!entryKey || !entryData) {
      return res.status(400).json({ error: 'entryKey and entryData are required' });
    }
    const config = readConfig(req.params.key);
    if (!config) {
      return res.status(404).json({ error: `Config file not found: ${req.params.key}` });
    }

    if (section && config[section]) {
      config[section][entryKey] = entryData;
    } else if (config.enemies) {
      config.enemies[entryKey] = entryData;
    } else if (config.affixes) {
      config.affixes[entryKey] = entryData;
    } else {
      config[entryKey] = entryData;
    }

    writeConfig(req.params.key, config);
    res.json({ success: true, key: req.params.key, entryKey });
  } catch (err) {
    res.status(500).json({ error: `Failed to update entry: ${err.message}` });
  }
});

// ── DELETE /api/config/:key/entry/:entryKey — delete an entry ─
app.delete('/api/config/:key/entry/:entryKey', (req, res) => {
  try {
    const { section } = req.query;
    const config = readConfig(req.params.key);
    if (!config) {
      return res.status(404).json({ error: `Config file not found: ${req.params.key}` });
    }

    const entryKey = req.params.entryKey;

    if (section && config[section]) {
      delete config[section][entryKey];
    } else if (config.enemies) {
      delete config.enemies[entryKey];
    } else if (config.affixes) {
      delete config.affixes[entryKey];
    } else {
      delete config[entryKey];
    }

    writeConfig(req.params.key, config);
    res.json({ success: true, key: req.params.key, deleted: entryKey });
  } catch (err) {
    res.status(500).json({ error: `Failed to delete entry: ${err.message}` });
  }
});

// ── GET /api/roster — parse floor enemy roster from dungeon_generator.py ──
app.get('/api/roster', (_req, res) => {
  try {
    if (!fs.existsSync(DUNGEON_GEN_PATH)) {
      return res.status(404).json({ error: 'dungeon_generator.py not found' });
    }
    const pySource = fs.readFileSync(DUNGEON_GEN_PATH, 'utf-8');

    // Extract the _FLOOR_ENEMY_ROSTER block
    const startMarker = '_FLOOR_ENEMY_ROSTER';
    const startIdx = pySource.indexOf(startMarker);
    if (startIdx === -1) {
      return res.status(404).json({ error: '_FLOOR_ENEMY_ROSTER not found in dungeon_generator.py' });
    }

    // Find the opening bracket and its matching close
    const listStart = pySource.indexOf('[', startIdx);
    let depth = 0;
    let listEnd = -1;
    for (let i = listStart; i < pySource.length; i++) {
      if (pySource[i] === '[') depth++;
      if (pySource[i] === ']') { depth--; if (depth === 0) { listEnd = i + 1; break; } }
    }

    if (listEnd === -1) {
      return res.status(500).json({ error: 'Could not parse roster list bounds' });
    }

    const rosterRaw = pySource.substring(listStart, listEnd);

    // Parse the Python literal into JS —
    // Each entry is: (max_floor, { "pool_name": [("enemy_type", weight), ...] })
    const tiers = [];
    // Match each (number, { ... }) tuple
    const tierRegex = /\(\s*(\d+)\s*,\s*\{([^}]*(?:\{[^}]*\}[^}]*)*)\s*\}\s*\)/gs;
    let match;
    while ((match = tierRegex.exec(rosterRaw)) !== null) {
      const maxFloor = parseInt(match[1]);
      const poolsRaw = match[2];
      const pools = {};

      // Match each "pool_name": [...] within the dict
      const poolRegex = /"(\w+)"\s*:\s*\[((?:[^\]]*\([^\)]*\)\s*,?\s*)*)\]/g;
      let poolMatch;
      while ((poolMatch = poolRegex.exec(poolsRaw)) !== null) {
        const poolName = poolMatch[1];
        const entriesRaw = poolMatch[2];
        const entries = [];
        const entryRegex = /\("(\w+)"\s*,\s*([\d.]+)\)/g;
        let entryMatch;
        while ((entryMatch = entryRegex.exec(entriesRaw)) !== null) {
          entries.push({ enemy_type: entryMatch[1], weight: parseFloat(entryMatch[2]) });
        }
        pools[poolName] = entries;
      }

      tiers.push({ max_floor: maxFloor, pools });
    }

    res.json({ tiers });
  } catch (err) {
    res.status(500).json({ error: `Failed to parse roster: ${err.message}` });
  }
});

// ── GET /api/sprites — sprite atlas data for the sprite picker ──
app.get('/api/sprites', (_req, res) => {
  try {
    if (!fs.existsSync(SPRITE_ATLAS_PATH)) {
      return res.status(404).json({ error: 'Sprite atlas not found' });
    }
    const raw = fs.readFileSync(SPRITE_ATLAS_PATH, 'utf-8');
    const atlas = JSON.parse(raw);

    // Return the atlas metadata + all sprites (the UI will filter by category)
    res.json({
      sheetFile: atlas.sheetFile || null,
      sheetWidth: atlas.sheetWidth || 0,
      sheetHeight: atlas.sheetHeight || 0,
      categories: atlas.categories || [],
      sprites: atlas.sprites || {},
    });
  } catch (err) {
    res.status(500).json({ error: `Failed to read sprite atlas: ${err.message}` });
  }
});

// ── GET /spritesheet.png — serve the combined character spritesheet ──
app.get('/spritesheet.png', (_req, res) => {
  if (!fs.existsSync(SPRITE_SHEET_PATH)) {
    return res.status(404).send('Spritesheet not found');
  }
  res.sendFile(SPRITE_SHEET_PATH);
});

// ── GET /api/enemy-meta — metadata for the UI ────────
app.get('/api/enemy-meta', (_req, res) => {
  res.json({
    roles: [
      'Swarm', 'Melee Bruiser', 'Melee Elite', 'Ranged Sniper',
      'Caster DPS', 'Debuff Caster', 'Tank', 'Enemy Healer',
      'Enemy Support', 'Elite — Imp Commander', 'Elite — Armored Demon',
      'Elite — Aberration', 'Boss — Room Guardian', 'Boss — Death Caster',
      'Boss — Demon Overlord', 'Boss — Arcane Construct', 'Boss — Death Mage',
      'Novelty — Armored Pest', 'Melee — Fast Undead', 'Melee — Shadow Creature',
      'Melee — Humanoid Fodder', 'Ranged — Skeleton Mage', 'Ranged — Generic Mage',
      'Swarm — Bug', 'Target Dummy',
    ],
    ai_behaviors: ['aggressive', 'ranged', 'support', 'boss', 'dummy'],
    tags: ['undead', 'demon', 'beast', 'construct', 'aberration', 'humanoid'],
    shapes: ['circle', 'square', 'diamond', 'triangle', 'star', 'hexagon'],
    rarity_tiers: ['normal', 'champion', 'rare', 'super_unique'],
    affix_categories: ['offensive', 'defensive', 'mobility', 'on_death', 'on_hit', 'retaliation', 'disruption', 'debuff', 'sustain'],
    rarity_colors: {
      normal:       '#ffffff',
      champion:     '#6688ff',
      rare:         '#ffcc00',
      super_unique: '#cc66ff',
    },
    champion_type_ids: ['berserker', 'fanatic', 'ghostly', 'resilient', 'possessed'],
  });
});

// ── Start server ──────────────────────────────────────
app.listen(PORT, () => {
  console.log(`\n  👹 Enemy Forge API running at http://localhost:${PORT}`);
  console.log(`  📁 Configs dir: ${CONFIGS_DIR}\n`);
  for (const [key, filepath] of Object.entries(CONFIG_FILES)) {
    const exists = fs.existsSync(filepath);
    console.log(`  ${exists ? '✅' : '❌'} ${key}: ${path.basename(filepath)}`);
  }
  console.log(`\n  📜 Roster source: ${fs.existsSync(DUNGEON_GEN_PATH) ? '✅' : '❌'} dungeon_generator.py\n`);
});
