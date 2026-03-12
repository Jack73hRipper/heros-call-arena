// ─────────────────────────────────────────────────────────
// server.js — Micro API for Item Forge (config file I/O)
// ─────────────────────────────────────────────────────────
// Provides read/write access to all item-related JSON configs:
//   - affixes_config.json
//   - items_config.json
//   - uniques_config.json
//   - item_names_config.json
//   - loot_tables.json
//   - combat_config.json
//   - sets_config.json (when it exists)

import express from 'express';
import cors from 'cors';
import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const app = express();
const PORT = 5221;

// Paths relative to project root
const PROJECT_ROOT = path.resolve(__dirname, '../..');
const CONFIGS_DIR = path.join(PROJECT_ROOT, 'server', 'configs');

// Config file registry — each key maps to a JSON file
const CONFIG_FILES = {
  affixes:      path.join(CONFIGS_DIR, 'affixes_config.json'),
  items:        path.join(CONFIGS_DIR, 'items_config.json'),
  uniques:      path.join(CONFIGS_DIR, 'uniques_config.json'),
  item_names:   path.join(CONFIGS_DIR, 'item_names_config.json'),
  loot_tables:  path.join(CONFIGS_DIR, 'loot_tables.json'),
  combat:       path.join(CONFIGS_DIR, 'combat_config.json'),
  sets:         path.join(CONFIGS_DIR, 'sets_config.json'),
};

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

    // If section is specified (e.g., "prefixes" inside affixes_config),
    // update within that section
    if (section && config[section]) {
      config[section][entryKey] = entryData;
    } else if (config.items) {
      config.items[entryKey] = entryData;
    } else if (config.uniques) {
      config.uniques[entryKey] = entryData;
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
    } else if (config.items) {
      delete config.items[entryKey];
    } else if (config.uniques) {
      delete config.uniques[entryKey];
    } else {
      delete config[entryKey];
    }

    writeConfig(req.params.key, config);
    res.json({ success: true, key: req.params.key, deleted: entryKey });
  } catch (err) {
    res.status(500).json({ error: `Failed to delete entry: ${err.message}` });
  }
});

// ── GET /api/stats-meta — stat metadata for the UI ────
app.get('/api/stats-meta', (_req, res) => {
  res.json({
    stats: {
      attack_damage:         { label: 'Melee Damage',      type: 'int',   unit: '',   budget_pts: 1.0 },
      ranged_damage:         { label: 'Ranged Damage',     type: 'int',   unit: '',   budget_pts: 1.0 },
      armor:                 { label: 'Armor',             type: 'int',   unit: '',   budget_pts: 1.5 },
      max_hp:                { label: 'Max HP',            type: 'int',   unit: '',   budget_pts: 0.2 },
      crit_chance:           { label: 'Crit Chance',       type: 'float', unit: '%',  budget_pts: 200,  cap: 0.50 },
      crit_damage:           { label: 'Crit Damage',       type: 'float', unit: '%',  budget_pts: 150,  cap: 3.0 },
      dodge_chance:          { label: 'Dodge Chance',      type: 'float', unit: '%',  budget_pts: 200,  cap: 0.40 },
      damage_reduction_pct:  { label: 'Damage Reduction',  type: 'float', unit: '%',  budget_pts: 250,  cap: 0.50 },
      hp_regen:              { label: 'HP Regen',          type: 'int',   unit: '/t', budget_pts: 1.5 },
      move_speed:            { label: 'Move Speed',        type: 'int',   unit: '',   budget_pts: 5.0,  cap: 2 },
      life_on_hit:           { label: 'Life on Hit',       type: 'int',   unit: '',   budget_pts: 2.0 },
      cooldown_reduction_pct:{ label: 'CDR',               type: 'float', unit: '%',  budget_pts: 200,  cap: 0.30 },
      skill_damage_pct:      { label: 'Skill Damage',      type: 'float', unit: '%',  budget_pts: 150 },
      thorns:                { label: 'Thorns',            type: 'int',   unit: '',   budget_pts: 1.0,  cap: 12 },
      gold_find_pct:         { label: 'Gold Find',         type: 'float', unit: '%',  budget_pts: 50 },
      magic_find_pct:        { label: 'Magic Find',        type: 'float', unit: '%',  budget_pts: 100,  cap: 0.60 },
      holy_damage_pct:       { label: 'Holy Damage',       type: 'float', unit: '%',  budget_pts: 150 },
      dot_damage_pct:        { label: 'DoT Damage',        type: 'float', unit: '%',  budget_pts: 150 },
      heal_power_pct:        { label: 'Heal Power',        type: 'float', unit: '%',  budget_pts: 150 },
      armor_pen:             { label: 'Armor Pen',         type: 'int',   unit: '',   budget_pts: 2.0 },
    },
    rarity_colors: {
      common:   '#9d9d9d',
      magic:    '#4488ff',
      rare:     '#ffcc00',
      epic:     '#b040ff',
      unique:   '#ff8800',
      set:      '#00cc44',
    },
    rarity_order: ['common', 'magic', 'rare', 'epic', 'unique', 'set'],
    rarity_affix_counts: {
      common: { min: 0, max: 0 },
      magic:  { min: 1, max: 2 },
      rare:   { min: 3, max: 4 },
      epic:   { min: 4, max: 5 },
    },
    rarity_sell_multipliers: {
      common: 1.0,
      magic:  1.5,
      rare:   3.0,
      epic:   6.0,
      unique: 8.0,
      set:    8.0,
    },
    stat_budget_ranges: {
      common: { min: 5,  max: 10 },
      magic:  { min: 10, max: 20 },
      rare:   { min: 20, max: 35 },
      epic:   { min: 35, max: 50 },
      unique: { min: 40, max: 60 },
      set:    { min: 25, max: 35 },
    },
    equip_slots: ['weapon', 'armor', 'accessory', 'helmet', 'boots'],
  });
});

// ── Start server ──────────────────────────────────────
app.listen(PORT, () => {
  console.log(`\n  ⚒️  Item Forge API running at http://localhost:${PORT}`);
  console.log(`  📁 Configs dir: ${CONFIGS_DIR}\n`);
  // List found config files
  for (const [key, filepath] of Object.entries(CONFIG_FILES)) {
    const exists = fs.existsSync(filepath);
    console.log(`  ${exists ? '✅' : '❌'} ${key}: ${path.basename(filepath)}`);
  }
  console.log('');
});
