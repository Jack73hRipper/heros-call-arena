import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const GAME_PRESETS_DIR = path.resolve(__dirname, '../../client/public/particle-presets');
const GAME_EFFECTS_FILE = path.resolve(__dirname, '../../client/public/particle-effects.json');
const GAME_PRESETS_INDEX = path.resolve(__dirname, '../../client/public/particle-presets.json');

/** Vite plugin — exposes API endpoints for reading/writing game preset files. */
function gamePresetsApi() {
  return {
    name: 'game-presets-api',
    configureServer(server) {
      // GET /api/game-presets — returns all game presets grouped by category file
      server.middlewares.use('/api/game-presets', (req, res, next) => {
        if (req.method !== 'GET') return next();
        try {
          const indexRaw = fs.readFileSync(GAME_PRESETS_INDEX, 'utf-8');
          const index = JSON.parse(indexRaw);
          const categoryFiles = index.files || [];
          const result = {};
          for (const relPath of categoryFiles) {
            const category = path.basename(relPath, '.json'); // e.g. "skills"
            const fullPath = path.resolve(path.dirname(GAME_PRESETS_INDEX), relPath);
            if (fs.existsSync(fullPath)) {
              const raw = fs.readFileSync(fullPath, 'utf-8');
              result[category] = JSON.parse(raw);
            }
          }
          res.setHeader('Content-Type', 'application/json');
          res.end(JSON.stringify(result));
        } catch (err) {
          res.statusCode = 500;
          res.end(JSON.stringify({ error: err.message }));
        }
      });

      // POST /api/game-presets/save — saves a preset to the correct category file
      server.middlewares.use('/api/game-presets/save', (req, res, next) => {
        if (req.method !== 'POST') return next();
        let body = '';
        req.on('data', chunk => { body += chunk; });
        req.on('end', () => {
          try {
            const { preset, category } = JSON.parse(body);
            if (!preset || !preset.name || !category) {
              res.statusCode = 400;
              res.end(JSON.stringify({ error: 'Missing preset or category' }));
              return;
            }
            const filePath = path.join(GAME_PRESETS_DIR, `${category}.json`);
            if (!fs.existsSync(filePath)) {
              res.statusCode = 404;
              res.end(JSON.stringify({ error: `Category file not found: ${category}.json` }));
              return;
            }
            const raw = fs.readFileSync(filePath, 'utf-8');
            const presets = JSON.parse(raw);
            // Strip internal metadata before saving
            const cleanPreset = { ...preset };
            delete cleanPreset.builtIn;
            delete cleanPreset._gameCategory;
            const idx = presets.findIndex(p => p.name === preset.name);
            if (idx !== -1) {
              presets[idx] = cleanPreset;
            } else {
              presets.push(cleanPreset);
            }
            fs.writeFileSync(filePath, JSON.stringify(presets, null, 2) + '\n', 'utf-8');
            res.setHeader('Content-Type', 'application/json');
            res.end(JSON.stringify({ ok: true, action: idx !== -1 ? 'updated' : 'added', category }));
          } catch (err) {
            res.statusCode = 500;
            res.end(JSON.stringify({ error: err.message }));
          }
        });
      });

      // GET /api/game-effects — returns the particle-effects.json trigger map
      server.middlewares.use('/api/game-effects', (req, res, next) => {
        if (req.method !== 'GET') return next();
        try {
          const raw = fs.readFileSync(GAME_EFFECTS_FILE, 'utf-8');
          res.setHeader('Content-Type', 'application/json');
          res.end(raw);
        } catch (err) {
          res.statusCode = 500;
          res.end(JSON.stringify({ error: err.message }));
        }
      });
    },
  };
}

export default defineConfig({
  plugins: [react(), gamePresetsApi()],
  server: {
    port: 5180,
    open: true,
  },
  build: {
    outDir: 'dist',
  },
});
