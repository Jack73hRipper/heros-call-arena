// ─────────────────────────────────────────────────────────
// server.js — Micro API for Audio Workbench (file I/O)
// ─────────────────────────────────────────────────────────
// Provides read/write access to audio-effects.json and
// lists audio files on disk. ~80 lines.

import express from 'express';
import cors from 'cors';
import fs from 'fs';
import path from 'path';
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

app.use(cors());
app.use(express.json({ limit: '10mb' }));

// Serve audio files statically so the browser can play them
app.use('/audio', express.static(AUDIO_DIR));

// Serve asset library files so the browser can preview them
app.use('/library', express.static(ASSET_LIBRARY_DIR));

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

app.listen(PORT, () => {
  console.log(`\n  Audio Workbench API listening on http://localhost:${PORT}`);
  console.log(`  Audio dir:  ${AUDIO_DIR}`);
  console.log(`  Config:     ${CONFIG_PATH}\n`);
});
