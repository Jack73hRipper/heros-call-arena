// ─────────────────────────────────────────────────────────
// server.js — Micro API for Arena Analyst (match history)
// ─────────────────────────────────────────────────────────
// Provides read-only access to match report JSON files in
// server/data/match_history/, plus aggregation endpoints
// for class balance, composition stats, and trends.
//
// Endpoints:
//   GET    /api/matches          — list all match summaries (with filters)
//   GET    /api/matches/:id      — full match report for a single match
//   DELETE /api/matches/:id      — delete a single match report
//   POST   /api/matches/clear    — clear all match history
//   GET    /api/class-stats      — aggregated class balance data
//   GET    /api/comp-stats       — composition win rate data
//   GET    /api/trends           — time-series aggregates

import express from 'express';
import cors from 'cors';
import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const app = express();
const PORT = 5241;

// Paths relative to project root
const PROJECT_ROOT = path.resolve(__dirname, '../..');
const MATCH_HISTORY_DIR = path.join(PROJECT_ROOT, 'server', 'data', 'match_history');

app.use(cors());
app.use(express.json());

// ── Helper: ensure match history directory exists ──────
function ensureDir() {
  if (!fs.existsSync(MATCH_HISTORY_DIR)) {
    fs.mkdirSync(MATCH_HISTORY_DIR, { recursive: true });
  }
}

// ── Helper: list all match report files ────────────────
function listMatchFiles() {
  ensureDir();
  return fs.readdirSync(MATCH_HISTORY_DIR)
    .filter(f => f.endsWith('.json'))
    .sort()
    .reverse(); // newest first
}

// ── Helper: read a match report JSON ───────────────────
function readMatch(filename) {
  const filePath = path.join(MATCH_HISTORY_DIR, filename);
  if (!fs.existsSync(filePath)) return null;
  const raw = fs.readFileSync(filePath, 'utf-8');
  return JSON.parse(raw);
}

// ── Helper: extract match ID from filename ─────────────
// Filenames: {timestamp}_{match_id}.json
function matchIdFromFilename(filename) {
  const base = filename.replace('.json', '');
  const parts = base.split('_');
  // timestamp is first part(s), match_id is last
  return parts.length > 1 ? parts.slice(1).join('_') : base;
}

// ── Helper: find filename by match ID ──────────────────
function findFileByMatchId(matchId) {
  const files = listMatchFiles();
  // Try exact filename match first
  const exact = files.find(f => f === `${matchId}.json`);
  if (exact) return exact;
  // Try matching the match_id portion
  return files.find(f => {
    const base = f.replace('.json', '');
    return base === matchId || base.endsWith(`_${matchId}`) || base.includes(matchId);
  });
}

// ── Helper: build match summary from full report ───────
function buildSummary(report, filename) {
  return {
    match_id:       report.match_id || matchIdFromFilename(filename),
    filename:       filename,
    timestamp:      report.timestamp || null,
    map_id:         report.map_id || null,
    match_type:     report.match_type || null,
    winner:         report.winner || null,
    duration_turns: report.duration_turns || null,
    mvp:            report.summary?.mvp || null,
    mvp_damage:     report.summary?.mvp_damage || null,
    team_a_kills:   report.summary?.team_a_kills || 0,
    team_b_kills:   report.summary?.team_b_kills || 0,
  };
}

// ═══════════════════════════════════════════════════════
// ENDPOINTS
// ═══════════════════════════════════════════════════════

// ── GET /api/matches — list match summaries ────────────
// Query params: ?type=pvp&map=open_arena&from=2026-03-01&to=2026-03-08
app.get('/api/matches', (req, res) => {
  try {
    const files = listMatchFiles();
    let summaries = [];

    for (const file of files) {
      try {
        const report = readMatch(file);
        if (!report) continue;
        summaries.push(buildSummary(report, file));
      } catch {
        // Skip corrupted files
        continue;
      }
    }

    // Apply filters
    const { type, map, from, to } = req.query;

    if (type) {
      summaries = summaries.filter(m => m.match_type === type);
    }
    if (map) {
      summaries = summaries.filter(m => m.map_id === map);
    }
    if (from) {
      const fromDate = new Date(from);
      summaries = summaries.filter(m => m.timestamp && new Date(m.timestamp) >= fromDate);
    }
    if (to) {
      const toDate = new Date(to);
      toDate.setDate(toDate.getDate() + 1); // inclusive end
      summaries = summaries.filter(m => m.timestamp && new Date(m.timestamp) < toDate);
    }

    res.json(summaries);
  } catch (err) {
    res.status(500).json({ error: `Failed to list matches: ${err.message}` });
  }
});

// ── GET /api/matches/:id — full match report ──────────
app.get('/api/matches/:id', (req, res) => {
  try {
    const filename = findFileByMatchId(req.params.id);
    if (!filename) {
      return res.status(404).json({ error: `Match not found: ${req.params.id}` });
    }
    const report = readMatch(filename);
    if (!report) {
      return res.status(404).json({ error: `Match file unreadable: ${filename}` });
    }
    res.json(report);
  } catch (err) {
    res.status(500).json({ error: `Failed to read match: ${err.message}` });
  }
});

// ── DELETE /api/matches/:id — delete a match ──────────
app.delete('/api/matches/:id', (req, res) => {
  try {
    const filename = findFileByMatchId(req.params.id);
    if (!filename) {
      return res.status(404).json({ error: `Match not found: ${req.params.id}` });
    }
    const filePath = path.join(MATCH_HISTORY_DIR, filename);
    fs.unlinkSync(filePath);
    res.json({ success: true, deleted: filename });
  } catch (err) {
    res.status(500).json({ error: `Failed to delete match: ${err.message}` });
  }
});

// ── POST /api/matches/clear — clear all history ───────
app.post('/api/matches/clear', (req, res) => {
  try {
    const files = listMatchFiles();
    let deleted = 0;
    for (const file of files) {
      try {
        fs.unlinkSync(path.join(MATCH_HISTORY_DIR, file));
        deleted++;
      } catch { /* skip */ }
    }
    res.json({ success: true, deleted });
  } catch (err) {
    res.status(500).json({ error: `Failed to clear matches: ${err.message}` });
  }
});

// ── GET /api/class-stats — aggregated class balance ───
app.get('/api/class-stats', (req, res) => {
  try {
    const files = listMatchFiles();
    const classData = {}; // class_id → { matches, wins, losses, dmg[], heal[], kills[], deaths[] }

    for (const file of files) {
      try {
        const report = readMatch(file);
        if (!report || !report.unit_stats || !report.teams) continue;

        const winner = report.winner;

        // Collect per-unit stats grouped by class
        for (const [unitId, stats] of Object.entries(report.unit_stats)) {
          const classId = stats.class_id;
          if (!classId) continue;

          if (!classData[classId]) {
            classData[classId] = {
              class_id: classId,
              matches: 0,
              wins: 0,
              losses: 0,
              total_damage: 0,
              total_healing: 0,
              total_kills: 0,
              total_deaths: 0,
              appearances: 0,
            };
          }

          const cd = classData[classId];
          cd.appearances++;

          // Determine if this unit's team won
          const unitTeam = stats.team;
          const teamWon = (unitTeam === 'a' && winner === 'team_a') ||
                          (unitTeam === 'b' && winner === 'team_b');

          cd.total_damage  += stats.damage_dealt || 0;
          cd.total_healing += stats.healing_done || 0;
          cd.total_kills   += stats.kills || 0;
          cd.total_deaths  += stats.deaths || 0;

          if (teamWon) cd.wins++;
          else cd.losses++;
        }
      } catch { continue; }
    }

    // Compute averages & win rates
    const result = Object.values(classData).map(cd => ({
      class_id:     cd.class_id,
      appearances:  cd.appearances,
      wins:         cd.wins,
      losses:       cd.losses,
      win_rate:     cd.appearances > 0 ? Math.round((cd.wins / cd.appearances) * 1000) / 10 : 0,
      avg_damage:   cd.appearances > 0 ? Math.round(cd.total_damage / cd.appearances) : 0,
      avg_healing:  cd.appearances > 0 ? Math.round(cd.total_healing / cd.appearances) : 0,
      avg_kills:    cd.appearances > 0 ? Math.round((cd.total_kills / cd.appearances) * 10) / 10 : 0,
      avg_deaths:   cd.appearances > 0 ? Math.round((cd.total_deaths / cd.appearances) * 10) / 10 : 0,
    }));

    result.sort((a, b) => b.win_rate - a.win_rate);
    res.json(result);
  } catch (err) {
    res.status(500).json({ error: `Failed to compute class stats: ${err.message}` });
  }
});

// ── GET /api/comp-stats — composition win rates ───────
app.get('/api/comp-stats', (req, res) => {
  try {
    const files = listMatchFiles();
    const compData = {}; // comp_key → { comp_classes, matches, wins, losses }

    for (const file of files) {
      try {
        const report = readMatch(file);
        if (!report || !report.teams) continue;

        const winner = report.winner;

        for (const [teamKey, roster] of Object.entries(report.teams)) {
          if (!Array.isArray(roster)) continue;

          // Build comp key: sorted list of class_ids
          const classes = roster.map(u => u.class_id).filter(Boolean).sort();
          const compKey = classes.join('+');
          if (!compKey) continue;

          if (!compData[compKey]) {
            compData[compKey] = {
              comp_key: compKey,
              classes: classes,
              matches: 0,
              wins: 0,
              losses: 0,
            };
          }

          const cd = compData[compKey];
          cd.matches++;

          const teamWon = (teamKey === 'team_a' && winner === 'team_a') ||
                          (teamKey === 'team_b' && winner === 'team_b');
          if (teamWon) cd.wins++;
          else cd.losses++;
        }
      } catch { continue; }
    }

    const result = Object.values(compData)
      .map(cd => ({
        ...cd,
        win_rate: cd.matches > 0 ? Math.round((cd.wins / cd.matches) * 1000) / 10 : 0,
      }))
      .sort((a, b) => b.matches - a.matches);

    res.json(result);
  } catch (err) {
    res.status(500).json({ error: `Failed to compute comp stats: ${err.message}` });
  }
});

// ── GET /api/trends — time-series aggregates ──────────
app.get('/api/trends', (req, res) => {
  try {
    const files = listMatchFiles();
    const dayBuckets = {}; // date_str → { matches, team_a_wins, team_b_wins, draws, total_turns, total_damage }

    for (const file of files) {
      try {
        const report = readMatch(file);
        if (!report || !report.timestamp) continue;

        const dateStr = report.timestamp.substring(0, 10); // YYYY-MM-DD

        if (!dayBuckets[dateStr]) {
          dayBuckets[dateStr] = {
            date: dateStr,
            matches: 0,
            team_a_wins: 0,
            team_b_wins: 0,
            draws: 0,
            total_turns: 0,
            total_damage: 0,
          };
        }

        const bucket = dayBuckets[dateStr];
        bucket.matches++;
        bucket.total_turns += report.duration_turns || 0;

        if (report.winner === 'team_a') bucket.team_a_wins++;
        else if (report.winner === 'team_b') bucket.team_b_wins++;
        else bucket.draws++;

        // Sum total damage from summary
        bucket.total_damage += (report.summary?.team_a_total_damage || 0) +
                               (report.summary?.team_b_total_damage || 0);
      } catch { continue; }
    }

    const result = Object.values(dayBuckets)
      .map(b => ({
        ...b,
        avg_turns:  b.matches > 0 ? Math.round(b.total_turns / b.matches) : 0,
        avg_damage: b.matches > 0 ? Math.round(b.total_damage / b.matches) : 0,
      }))
      .sort((a, b) => a.date.localeCompare(b.date));

    res.json(result);
  } catch (err) {
    res.status(500).json({ error: `Failed to compute trends: ${err.message}` });
  }
});

// ── Start server ──────────────────────────────────────
app.listen(PORT, () => {
  ensureDir();
  const fileCount = listMatchFiles().length;
  console.log(`\n  📊 Arena Analyst API running at http://localhost:${PORT}`);
  console.log(`  📁 Match history dir: ${MATCH_HISTORY_DIR}`);
  console.log(`  📄 Match reports found: ${fileCount}\n`);
});
