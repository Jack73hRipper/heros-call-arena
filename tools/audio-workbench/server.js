// ─────────────────────────────────────────────────────────
// server.js — Micro API for Audio Workbench (file I/O)
// ─────────────────────────────────────────────────────────
// Provides read/write access to audio-effects.json and
// lists audio files on disk. ~80 lines.

import express from 'express';
import cors from 'cors';
import fs from 'fs';
import path from 'path';
import { execFile } from 'child_process';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const app = express();
const PORT = 5211;

// Paths relative to project root
const PROJECT_ROOT = path.resolve(__dirname, '../..');
const AUDIO_DIR = path.join(PROJECT_ROOT, 'client', 'public', 'audio');
const CONFIG_PATH = path.join(PROJECT_ROOT, 'client', 'public', 'audio-effects.json');
const ASSET_LIBRARY_DIR = path.join(PROJECT_ROOT, 'Assets', 'Audio', "Helton Yan's Pixel Combat - Single Files");
const SYNTH_DIR = path.join(__dirname, 'synth', 'generated');
const SYNTH_SCRIPT = path.join(__dirname, 'synth', 'generate_sfx.py');

app.use(cors());
app.use(express.json({ limit: '10mb' }));

// Serve audio files statically so the browser can play them
app.use('/audio', express.static(AUDIO_DIR));

// Serve asset library files so the browser can preview them
app.use('/library', express.static(ASSET_LIBRARY_DIR));

// Serve synthesized sound files for preview
app.use('/audio-synth', express.static(SYNTH_DIR));

// GET /api/config — read audio-effects.json
app.get('/api/config', (_req, res) => {
  try {
    const raw = fs.readFileSync(CONFIG_PATH, 'utf-8');
    res.json(JSON.parse(raw));
  } catch (err) {
    res.status(500).json({ error: `Failed to read config: ${err.message}` });
  }
});

// POST /api/config — write updated audio-effects.json
app.post('/api/config', (req, res) => {
  try {
    const json = JSON.stringify(req.body, null, 2);
    // Create a backup before overwriting
    const backupPath = CONFIG_PATH.replace('.json', `.backup-${Date.now()}.json`);
    if (fs.existsSync(CONFIG_PATH)) {
      fs.copyFileSync(CONFIG_PATH, backupPath);
    }
    fs.writeFileSync(CONFIG_PATH, json, 'utf-8');
    // Clean old backups — keep only last 5
    const dir = path.dirname(CONFIG_PATH);
    const backups = fs.readdirSync(dir)
      .filter(f => f.startsWith('audio-effects.backup-') && f.endsWith('.json'))
      .sort()
      .reverse();
    backups.slice(5).forEach(f => fs.unlinkSync(path.join(dir, f)));
    res.json({ success: true, backup: path.basename(backupPath) });
  } catch (err) {
    res.status(500).json({ error: `Failed to write config: ${err.message}` });
  }
});

// GET /api/sounds — recursively list all audio files on disk
app.get('/api/sounds', (_req, res) => {
  try {
    const files = [];
    function walk(dir, rel) {
      const entries = fs.readdirSync(dir, { withFileTypes: true });
      for (const entry of entries) {
        const fullPath = path.join(dir, entry.name);
        const relPath = path.join(rel, entry.name).replace(/\\/g, '/');
        if (entry.isDirectory()) {
          walk(fullPath, relPath);
        } else if (/\.(wav|mp3|ogg|flac)$/i.test(entry.name)) {
          const stat = fs.statSync(fullPath);
          files.push({
            name: entry.name,
            path: `/audio/${relPath}`,
            category: rel.split('/')[0] || 'root',
            size: stat.size,
            modified: stat.mtime.toISOString(),
          });
        }
      }
    }
    walk(AUDIO_DIR, '');
    res.json({ files, totalCount: files.length });
  } catch (err) {
    res.status(500).json({ error: `Failed to list sounds: ${err.message}` });
  }
});

// GET /api/categories — list audio subdirectories
app.get('/api/categories', (_req, res) => {
  try {
    const entries = fs.readdirSync(AUDIO_DIR, { withFileTypes: true });
    const categories = entries
      .filter(e => e.isDirectory())
      .map(e => e.name);
    res.json({ categories });
  } catch (err) {
    res.status(500).json({ error: `Failed to list categories: ${err.message}` });
  }
});

// POST /api/import — copy/move file to a category folder
app.post('/api/import', (req, res) => {
  const { sourcePath, category, fileName } = req.body;
  if (!sourcePath || !category || !fileName) {
    return res.status(400).json({ error: 'Missing sourcePath, category, or fileName' });
  }
  try {
    const destDir = path.join(AUDIO_DIR, category);
    if (!fs.existsSync(destDir)) {
      fs.mkdirSync(destDir, { recursive: true });
    }
    const destPath = path.join(destDir, fileName);
    fs.copyFileSync(sourcePath, destPath);
    res.json({ success: true, path: `/audio/${category}/${fileName}` });
  } catch (err) {
    res.status(500).json({ error: `Failed to import: ${err.message}` });
  }
});

// GET /api/library — list all files in the Helton Yan asset library
app.get('/api/library', (_req, res) => {
  try {
    if (!fs.existsSync(ASSET_LIBRARY_DIR)) {
      return res.json({ files: [], totalCount: 0, available: false });
    }
    const files = [];
    const entries = fs.readdirSync(ASSET_LIBRARY_DIR, { withFileTypes: true });
    for (const entry of entries) {
      if (!entry.isFile()) continue;
      if (!/\.(wav|mp3|ogg|flac)$/i.test(entry.name)) continue;
      const fullPath = path.join(ASSET_LIBRARY_DIR, entry.name);
      const stat = fs.statSync(fullPath);
      // Parse category from filename convention: PREFIX_CATEGORY-Name_HY_PC-NNN.wav
      const match = entry.name.match(/^[A-Z]+_([A-Z\s]+)-/i);
      const category = match ? match[1].trim() : 'unknown';
      // Parse descriptive name
      const nameMatch = entry.name.match(/^[A-Z]+_[A-Z\s]+-(.+?)_HY_PC/i);
      const displayName = nameMatch ? nameMatch[1].replace(/_/g, ' ') : entry.name;
      // Parse variant number
      const varMatch = entry.name.match(/-(\d{3})\.wav$/i);
      const variant = varMatch ? parseInt(varMatch[1]) : 1;
      files.push({
        name: entry.name,
        displayName,
        category,
        variant,
        size: stat.size,
        previewPath: `/library/${encodeURIComponent(entry.name)}`,
        absolutePath: fullPath,
      });
    }
    // Sort by category, then displayName, then variant
    files.sort((a, b) =>
      a.category.localeCompare(b.category) ||
      a.displayName.localeCompare(b.displayName) ||
      a.variant - b.variant
    );
    res.json({ files, totalCount: files.length, available: true });
  } catch (err) {
    res.status(500).json({ error: `Failed to list library: ${err.message}` });
  }
});

// POST /api/library/import — copy a library file to the game audio folder
app.post('/api/library/import', (req, res) => {
  const { libraryFileName, category, newFileName } = req.body;
  if (!libraryFileName || !category) {
    return res.status(400).json({ error: 'Missing libraryFileName or category' });
  }
  try {
    const sourcePath = path.join(ASSET_LIBRARY_DIR, libraryFileName);
    if (!fs.existsSync(sourcePath)) {
      return res.status(404).json({ error: `Library file not found: ${libraryFileName}` });
    }
    const destDir = path.join(AUDIO_DIR, category);
    if (!fs.existsSync(destDir)) {
      fs.mkdirSync(destDir, { recursive: true });
    }
    const finalName = newFileName || libraryFileName;
    const destPath = path.join(destDir, finalName);
    fs.copyFileSync(sourcePath, destPath);
    const stat = fs.statSync(destPath);
    res.json({
      success: true,
      path: `/audio/${category}/${finalName}`,
      size: stat.size,
    });
  } catch (err) {
    res.status(500).json({ error: `Failed to import: ${err.message}` });
  }
});

// ─────────────────────────────────────────────────────────
// Synthesizer endpoints
// ─────────────────────────────────────────────────────────

// GET /api/synth/manifest — read the generated manifest (if exists)
app.get('/api/synth/manifest', (_req, res) => {
  try {
    const manifestPath = path.join(SYNTH_DIR, 'generated-manifest.json');
    if (!fs.existsSync(manifestPath)) {
      return res.json({ generated: false, sounds: [], totalCount: 0 });
    }
    const raw = fs.readFileSync(manifestPath, 'utf-8');
    res.json(JSON.parse(raw));
  } catch (err) {
    res.status(500).json({ error: `Failed to read manifest: ${err.message}` });
  }
});

// POST /api/synth/generate — run the Python synth script to generate all sounds
app.post('/api/synth/generate', (_req, res) => {
  const python = path.join(PROJECT_ROOT, '.venv', 'Scripts', 'python.exe');
  const pythonFallback = 'python';

  const pyExe = fs.existsSync(python) ? python : pythonFallback;

  execFile(pyExe, [SYNTH_SCRIPT, '--out', SYNTH_DIR], {
    cwd: path.dirname(SYNTH_SCRIPT),
    timeout: 60000,
  }, (err, stdout, stderr) => {
    if (err) {
      return res.status(500).json({
        error: `Synth script failed: ${err.message}`,
        stdout,
        stderr,
      });
    }
    // Read manifest after generation
    try {
      const manifestPath = path.join(SYNTH_DIR, 'generated-manifest.json');
      const raw = fs.readFileSync(manifestPath, 'utf-8');
      const manifest = JSON.parse(raw);
      res.json({ success: true, ...manifest, stdout });
    } catch (readErr) {
      res.json({ success: true, stdout, stderr });
    }
  });
});

// POST /api/synth/apply — copy a synth sound into the game audio folder + update config
app.post('/api/synth/apply', (req, res) => {
  const { key, category, filename } = req.body;
  if (!key || !category || !filename) {
    return res.status(400).json({ error: 'Missing key, category, or filename' });
  }
  try {
    const sourcePath = path.join(SYNTH_DIR, category, filename);
    if (!fs.existsSync(sourcePath)) {
      return res.status(404).json({ error: `Synth file not found: ${category}/${filename}` });
    }
    const destDir = path.join(AUDIO_DIR, category);
    if (!fs.existsSync(destDir)) {
      fs.mkdirSync(destDir, { recursive: true });
    }
    const destPath = path.join(destDir, filename);
    fs.copyFileSync(sourcePath, destPath);
    const stat = fs.statSync(destPath);
    const gamePath = `/audio/${category}/${filename}`;

    // Update audio-effects.json _soundFiles
    const raw = fs.readFileSync(CONFIG_PATH, 'utf-8');
    const config = JSON.parse(raw);
    if (config._soundFiles) {
      config._soundFiles[key] = gamePath;
      // Backup + save
      const backupPath = CONFIG_PATH.replace('.json', `.backup-${Date.now()}.json`);
      fs.copyFileSync(CONFIG_PATH, backupPath);
      fs.writeFileSync(CONFIG_PATH, JSON.stringify(config, null, 2), 'utf-8');
      // Clean old backups
      const dir = path.dirname(CONFIG_PATH);
      const backups = fs.readdirSync(dir)
        .filter(f => f.startsWith('audio-effects.backup-') && f.endsWith('.json'))
        .sort()
        .reverse();
      backups.slice(5).forEach(f => fs.unlinkSync(path.join(dir, f)));
    }

    res.json({ success: true, path: gamePath, size: stat.size });
  } catch (err) {
    res.status(500).json({ error: `Failed to apply: ${err.message}` });
  }
});

// POST /api/synth/apply-all — copy ALL synth sounds into game audio + update config
app.post('/api/synth/apply-all', (_req, res) => {
  try {
    const manifestPath = path.join(SYNTH_DIR, 'generated-manifest.json');
    if (!fs.existsSync(manifestPath)) {
      return res.status(400).json({ error: 'No generated sounds — run generate first' });
    }
    const manifest = JSON.parse(fs.readFileSync(manifestPath, 'utf-8'));
    const raw = fs.readFileSync(CONFIG_PATH, 'utf-8');
    const config = JSON.parse(raw);

    // Backup config
    const backupPath = CONFIG_PATH.replace('.json', `.backup-${Date.now()}.json`);
    fs.copyFileSync(CONFIG_PATH, backupPath);

    let applied = 0;
    for (const sound of manifest.sounds) {
      const sourcePath = path.join(SYNTH_DIR, sound.category, sound.filename);
      if (!fs.existsSync(sourcePath)) continue;

      const destDir = path.join(AUDIO_DIR, sound.category);
      if (!fs.existsSync(destDir)) {
        fs.mkdirSync(destDir, { recursive: true });
      }
      const destPath = path.join(destDir, sound.filename);
      fs.copyFileSync(sourcePath, destPath);

      if (config._soundFiles) {
        config._soundFiles[sound.key] = `/audio/${sound.category}/${sound.filename}`;
      }
      applied++;
    }

    // Save updated config
    fs.writeFileSync(CONFIG_PATH, JSON.stringify(config, null, 2), 'utf-8');

    // Clean old backups
    const dir = path.dirname(CONFIG_PATH);
    const backups = fs.readdirSync(dir)
      .filter(f => f.startsWith('audio-effects.backup-') && f.endsWith('.json'))
      .sort()
      .reverse();
    backups.slice(5).forEach(f => fs.unlinkSync(path.join(dir, f)));

    res.json({ success: true, applied, total: manifest.sounds.length });
  } catch (err) {
    res.status(500).json({ error: `Failed to apply all: ${err.message}` });
  }
});

// ─────────────────────────────────────────────────────────
// Sound Editor endpoints — parameterized editing & presets
// ─────────────────────────────────────────────────────────

const PRESETS_PATH = path.join(__dirname, 'synth', 'synth-presets.json');

// GET /api/synth/editor/:key — get editor info for a sound key
app.get('/api/synth/editor/:key', (req, res) => {
  const python = fs.existsSync(path.join(PROJECT_ROOT, '.venv', 'Scripts', 'python.exe'))
    ? path.join(PROJECT_ROOT, '.venv', 'Scripts', 'python.exe')
    : 'python';

  const editorArgs = [SYNTH_SCRIPT, '--editor-info', req.params.key];
  if (req.query.template) editorArgs.push('--template', req.query.template);

  execFile(python, editorArgs, {
    cwd: path.dirname(SYNTH_SCRIPT),
    timeout: 10000,
  }, (err, stdout, stderr) => {
    if (err) {
      return res.status(500).json({ error: `Editor info failed: ${err.message}`, stderr });
    }
    try {
      const data = JSON.parse(stdout);
      // Merge saved preset overrides if they exist
      if (fs.existsSync(PRESETS_PATH)) {
        const presets = JSON.parse(fs.readFileSync(PRESETS_PATH, 'utf-8'));
        if (presets[req.params.key]) {
          const saved = presets[req.params.key].params || {};
          for (const p of data.params || []) {
            if (saved[p.key] !== undefined) {
              p.value = saved[p.key];
              p.customized = true;
            }
          }
        }
      }
      res.json(data);
    } catch (parseErr) {
      res.status(500).json({ error: `Failed to parse editor info`, stdout, stderr });
    }
  });
});

// GET /api/synth/templates — list all available templates
app.get('/api/synth/templates', (_req, res) => {
  const python = fs.existsSync(path.join(PROJECT_ROOT, '.venv', 'Scripts', 'python.exe'))
    ? path.join(PROJECT_ROOT, '.venv', 'Scripts', 'python.exe')
    : 'python';

  execFile(python, [SYNTH_SCRIPT, '--list-templates'], {
    cwd: path.dirname(SYNTH_SCRIPT),
    timeout: 10000,
  }, (err, stdout, stderr) => {
    if (err) {
      return res.status(500).json({ error: `Templates query failed: ${err.message}`, stderr });
    }
    try {
      res.json(JSON.parse(stdout));
    } catch (parseErr) {
      res.status(500).json({ error: 'Failed to parse templates', stdout, stderr });
    }
  });
});

// POST /api/synth/generate-one — generate a single sound with custom params
app.post('/api/synth/generate-one', (req, res) => {
  const { key, params, template } = req.body;
  if (!key) {
    return res.status(400).json({ error: 'Missing key' });
  }

  const python = fs.existsSync(path.join(PROJECT_ROOT, '.venv', 'Scripts', 'python.exe'))
    ? path.join(PROJECT_ROOT, '.venv', 'Scripts', 'python.exe')
    : 'python';

  const args = [SYNTH_SCRIPT, '--key', key, '--out', SYNTH_DIR];
  if (params) {
    args.push('--params-json', JSON.stringify(params));
  }
  if (template) {
    args.push('--template', template);
  }

  execFile(python, args, {
    cwd: path.dirname(SYNTH_SCRIPT),
    timeout: 30000,
  }, (err, stdout, stderr) => {
    if (err) {
      return res.status(500).json({ error: `Generation failed: ${err.message}`, stderr });
    }
    try {
      const data = JSON.parse(stdout);
      res.json(data);
    } catch (parseErr) {
      // Fallback: might be batch-style output for unknown key
      res.json({ success: true, stdout });
    }
  });
});

// GET /api/synth/presets — read saved presets
app.get('/api/synth/presets', (_req, res) => {
  try {
    if (!fs.existsSync(PRESETS_PATH)) {
      return res.json({ presets: {} });
    }
    const raw = fs.readFileSync(PRESETS_PATH, 'utf-8');
    res.json({ presets: JSON.parse(raw) });
  } catch (err) {
    res.status(500).json({ error: `Failed to read presets: ${err.message}` });
  }
});

// POST /api/synth/presets — save a preset for a sound key
app.post('/api/synth/presets', (req, res) => {
  const { key, template, params, category, filename, description } = req.body;
  if (!key) {
    return res.status(400).json({ error: 'Missing key' });
  }
  try {
    let presets = {};
    if (fs.existsSync(PRESETS_PATH)) {
      presets = JSON.parse(fs.readFileSync(PRESETS_PATH, 'utf-8'));
    }
    presets[key] = {
      template: template || null,
      params: params || {},
      category: category || 'custom',
      filename: filename || `${key}.wav`,
      description: description || '',
      savedAt: new Date().toISOString(),
    };
    fs.writeFileSync(PRESETS_PATH, JSON.stringify(presets, null, 2), 'utf-8');
    res.json({ success: true, key });
  } catch (err) {
    res.status(500).json({ error: `Failed to save preset: ${err.message}` });
  }
});

// DELETE /api/synth/presets/:key — delete a saved preset
app.delete('/api/synth/presets/:key', (req, res) => {
  try {
    if (!fs.existsSync(PRESETS_PATH)) {
      return res.json({ success: true });
    }
    const presets = JSON.parse(fs.readFileSync(PRESETS_PATH, 'utf-8'));
    delete presets[req.params.key];
    fs.writeFileSync(PRESETS_PATH, JSON.stringify(presets, null, 2), 'utf-8');
    res.json({ success: true });
  } catch (err) {
    res.status(500).json({ error: `Failed to delete preset: ${err.message}` });
  }
});

app.listen(PORT, () => {
  console.log(`\n  Audio Workbench API listening on http://localhost:${PORT}`);
  console.log(`  Audio dir:  ${AUDIO_DIR}`);
  console.log(`  Config:     ${CONFIG_PATH}\n`);
});
