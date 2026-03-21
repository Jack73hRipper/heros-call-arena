// ─────────────────────────────────────────────────────────
// server.js — PVPVE Analyst API
// ─────────────────────────────────────────────────────────
// Read-only API for PVPVE match report JSON files.
// Provides match listing, detail, 4-team scoreboard data,
// combat timeline, exploration stats, equipment reports,
// and batch aggregation.
//
// Endpoints:
//   GET  /api/matches              — list PVPVE match summaries
//   GET  /api/matches/:id          — full match report
//   GET  /api/matches/:id/timeline — timeline events for a match
//   GET  /api/team-stats           — per-team aggregate stats
//   GET  /api/class-stats          — per-class aggregate stats
//   GET  /api/batch-overview       — batch run aggregation

import express from 'express';
import cors from 'cors';
import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const app = express();
const PORT = 5242;

const PROJECT_ROOT = path.resolve(__dirname, '../..');
const MATCH_HISTORY_DIR = path.join(PROJECT_ROOT, 'server', 'data', 'match_history');

app.use(cors());
app.use(express.json());

// ── Helpers ───────────────────────────────────────────────

function ensureDir() {
  if (!fs.existsSync(MATCH_HISTORY_DIR)) {
    fs.mkdirSync(MATCH_HISTORY_DIR, { recursive: true });
  }
}

function listMatchFiles() {
  ensureDir();
  return fs.readdirSync(MATCH_HISTORY_DIR)
    .filter(f => f.endsWith('.json'))
    .sort()
    .reverse();
}

function readMatch(filename) {
  const filePath = path.join(MATCH_HISTORY_DIR, filename);
  if (!fs.existsSync(filePath)) return null;
  const raw = fs.readFileSync(filePath, 'utf-8');
  return JSON.parse(raw);
}

function findFileByMatchId(matchId) {
  const files = listMatchFiles();
  const exact = files.find(f => f === `${matchId}.json`);
  if (exact) return exact;
  return files.find(f => {
    const base = f.replace('.json', '');
    return base === matchId || base.endsWith(`_${matchId}`) || base.includes(matchId);
  });
}

/** Only return PVPVE matches */
function isPvpve(report) {
  return report && report.match_type === 'pvpve';
}

/** Build compact summary for match list */
function buildSummary(report, filename) {
  const unitStats = report.unit_stats || {};
  const summary = report.summary || {};

  // Count heroes vs PVE enemies
  let heroCount = 0;
  let pveCount = 0;
  let aliveHeroes = 0;
  for (const u of Object.values(unitStats)) {
    if (u.team === 'pve') { pveCount++; }
    else if (['a', 'b', 'c', 'd'].includes(u.team)) {
      heroCount++;
      if (u.status === 'survived') aliveHeroes++;
    }
  }

  // Team kill/death totals
  const teamStats = {};
  for (const tk of ['a', 'b', 'c', 'd']) {
    teamStats[tk] = { kills: 0, deaths: 0, damage: 0, healing: 0, alive: 0, total: 0 };
  }
  for (const u of Object.values(unitStats)) {
    const tk = u.team;
    if (!teamStats[tk]) continue;
    teamStats[tk].kills += u.kills || 0;
    teamStats[tk].deaths += u.deaths || 0;
    teamStats[tk].damage += u.damage_dealt || 0;
    teamStats[tk].healing += u.healing_done || 0;
    teamStats[tk].total++;
    if (u.status === 'survived') teamStats[tk].alive++;
  }

  return {
    match_id:       report.match_id,
    filename,
    timestamp:      report.timestamp || null,
    map_id:         report.map_id || null,
    match_type:     report.match_type,
    winner:         report.winner || null,
    duration_turns: report.duration_turns || null,
    hero_count:     heroCount,
    pve_count:      pveCount,
    alive_heroes:   aliveHeroes,
    mvp:            summary.mvp || null,
    mvp_damage:     summary.mvp_damage || null,
    team_stats:     teamStats,
  };
}

// ═══════════════════════════════════════════════════════
// ENDPOINTS
// ═══════════════════════════════════════════════════════

// ── GET /api/matches — PVPVE match summaries ──────────
app.get('/api/matches', (req, res) => {
  try {
    const files = listMatchFiles();
    let summaries = [];

    for (const file of files) {
      try {
        const report = readMatch(file);
        if (!isPvpve(report)) continue;
        summaries.push(buildSummary(report, file));
      } catch { continue; }
    }

    // Filters
    const { winner, from, to, limit } = req.query;
    if (winner) {
      summaries = summaries.filter(m => m.winner === winner);
    }
    if (from) {
      const fromDate = new Date(from);
      summaries = summaries.filter(m => m.timestamp && new Date(m.timestamp) >= fromDate);
    }
    if (to) {
      const toDate = new Date(to);
      toDate.setDate(toDate.getDate() + 1);
      summaries = summaries.filter(m => m.timestamp && new Date(m.timestamp) < toDate);
    }
    if (limit) {
      summaries = summaries.slice(0, parseInt(limit, 10));
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
    if (!filename) return res.status(404).json({ error: 'Match not found' });
    const report = readMatch(filename);
    if (!report) return res.status(404).json({ error: 'Match file unreadable' });
    res.json(report);
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

// ── GET /api/matches/:id/timeline — timeline events ───
app.get('/api/matches/:id/timeline', (req, res) => {
  try {
    const filename = findFileByMatchId(req.params.id);
    if (!filename) return res.status(404).json({ error: 'Match not found' });
    const report = readMatch(filename);
    if (!report) return res.status(404).json({ error: 'Match file unreadable' });

    // Build per-turn team HP snapshots + event counts
    const unitStats = report.unit_stats || {};
    const timeline = report.timeline || [];
    const turns = [];

    // Track running HP per unit
    const unitHP = {};
    for (const [uid, u] of Object.entries(unitStats)) {
      // Approximate starting HP from stats — max_hp isn't stored, use heuristic
      unitHP[uid] = { team: u.team, alive: true };
    }

    // Build HP per team on each turn from timeline events
    const teamHPHistory = { a: [], b: [], c: [], d: [], pve: [] };
    const eventCounts = [];

    for (const turnData of timeline) {
      const turn = turnData.turn;
      const events = turnData.events || [];
      let kills = 0, damage = 0, healing = 0, skills = 0, doors = 0;
      const deathsThisTurn = [];

      for (const ev of events) {
        if (ev.type === 'damage') {
          damage += ev.dmg || 0;
        } else if (ev.type === 'heal') {
          healing += ev.amt || 0;
        } else if (ev.type === 'death') {
          kills++;
          deathsThisTurn.push({ unit: ev.unit, killer: ev.killer });
        } else if (ev.type === 'skill') {
          skills++;
        } else if (ev.type === 'door') {
          doors++;
        }
      }

      eventCounts.push({ turn, kills, damage, healing, skills, doors, deaths: deathsThisTurn });
    }

    res.json({ timeline: eventCounts, total_turns: report.duration_turns });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

// ── GET /api/team-stats — aggregate per-team stats ────
app.get('/api/team-stats', (req, res) => {
  try {
    const files = listMatchFiles();
    const teamAgg = {};
    for (const tk of ['a', 'b', 'c', 'd']) {
      teamAgg[tk] = { wins: 0, matches: 0, total_kills: 0, total_deaths: 0,
                       total_damage: 0, total_healing: 0, total_survivors: 0, total_heroes: 0 };
    }
    let matchCount = 0;

    for (const file of files) {
      try {
        const report = readMatch(file);
        if (!isPvpve(report)) continue;
        matchCount++;

        const winner = report.winner;
        const unitStats = report.unit_stats || {};

        for (const u of Object.values(unitStats)) {
          const tk = u.team;
          if (!teamAgg[tk]) continue;
          teamAgg[tk].total_kills += u.kills || 0;
          teamAgg[tk].total_deaths += u.deaths || 0;
          teamAgg[tk].total_damage += u.damage_dealt || 0;
          teamAgg[tk].total_healing += u.healing_done || 0;
          teamAgg[tk].total_heroes++;
          if (u.status === 'survived') teamAgg[tk].total_survivors++;
        }

        for (const tk of ['a', 'b', 'c', 'd']) {
          teamAgg[tk].matches = matchCount;
          if (winner === tk || winner === `team_${tk}`) teamAgg[tk].wins++;
        }
      } catch { continue; }
    }

    res.json({ match_count: matchCount, teams: teamAgg });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

// ── GET /api/class-stats — per-class PVPVE stats ─────
app.get('/api/class-stats', (req, res) => {
  try {
    const files = listMatchFiles();
    const classData = {};

    for (const file of files) {
      try {
        const report = readMatch(file);
        if (!isPvpve(report)) continue;

        const winner = report.winner;
        const unitStats = report.unit_stats || {};

        for (const u of Object.values(unitStats)) {
          if (u.team === 'pve') continue; // skip PVE enemies
          const classId = u.class_id;
          if (!classId) continue;

          if (!classData[classId]) {
            classData[classId] = {
              class_id: classId, appearances: 0, wins: 0,
              total_damage: 0, total_healing: 0, total_kills: 0,
              total_deaths: 0, total_survived: 0, boss_kills: 0,
            };
          }

          const cd = classData[classId];
          cd.appearances++;
          cd.total_damage += u.damage_dealt || 0;
          cd.total_healing += u.healing_done || 0;
          cd.total_kills += u.kills || 0;
          cd.total_deaths += u.deaths || 0;
          cd.boss_kills += u.boss_kills || 0;
          if (u.status === 'survived') cd.total_survived++;

          const teamWon = u.team && (winner === u.team || winner === `team_${u.team}`);
          if (teamWon) cd.wins++;
        }
      } catch { continue; }
    }

    const result = Object.values(classData).map(cd => ({
      ...cd,
      win_rate: cd.appearances > 0 ? Math.round((cd.wins / cd.appearances) * 1000) / 10 : 0,
      survival_rate: cd.appearances > 0 ? Math.round((cd.total_survived / cd.appearances) * 1000) / 10 : 0,
      avg_damage: cd.appearances > 0 ? Math.round(cd.total_damage / cd.appearances) : 0,
      avg_healing: cd.appearances > 0 ? Math.round(cd.total_healing / cd.appearances) : 0,
      avg_kills: cd.appearances > 0 ? Math.round((cd.total_kills / cd.appearances) * 10) / 10 : 0,
      avg_deaths: cd.appearances > 0 ? Math.round((cd.total_deaths / cd.appearances) * 10) / 10 : 0,
    })).sort((a, b) => b.win_rate - a.win_rate);

    res.json(result);
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

// ── GET /api/batch-overview — batch aggregation ───────
app.get('/api/batch-overview', (req, res) => {
  try {
    const files = listMatchFiles();
    const dayBuckets = {};
    const winCounts = { a: 0, b: 0, c: 0, d: 0, draw: 0 };
    let totalMatches = 0;
    let totalTurns = 0;

    for (const file of files) {
      try {
        const report = readMatch(file);
        if (!isPvpve(report)) continue;
        totalMatches++;
        totalTurns += report.duration_turns || 0;

        // Winner
        const w = report.winner || 'draw';
        if (w === 'team_a' || w === 'a') winCounts.a++;
        else if (w === 'team_b' || w === 'b') winCounts.b++;
        else if (w === 'team_c' || w === 'c') winCounts.c++;
        else if (w === 'team_d' || w === 'd') winCounts.d++;
        else winCounts.draw++;

        // Day bucket
        const dateStr = (report.timestamp || '').substring(0, 10);
        if (dateStr) {
          if (!dayBuckets[dateStr]) {
            dayBuckets[dateStr] = { date: dateStr, matches: 0, total_turns: 0 };
          }
          dayBuckets[dateStr].matches++;
          dayBuckets[dateStr].total_turns += report.duration_turns || 0;
        }
      } catch { continue; }
    }

    const daily = Object.values(dayBuckets)
      .map(b => ({ ...b, avg_turns: b.matches > 0 ? Math.round(b.total_turns / b.matches) : 0 }))
      .sort((a, b) => a.date.localeCompare(b.date));

    res.json({
      total_matches: totalMatches,
      avg_turns: totalMatches > 0 ? Math.round(totalTurns / totalMatches) : 0,
      win_counts: winCounts,
      daily,
    });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

// ── Start ─────────────────────────────────────────────
app.listen(PORT, () => {
  ensureDir();
  const allFiles = listMatchFiles();
  const pvpveCount = allFiles.filter(f => {
    try { const r = readMatch(f); return isPvpve(r); } catch { return false; }
  }).length;
  console.log(`\n  ⚔  PVPVE Analyst API running at http://localhost:${PORT}`);
  console.log(`  📁 Match history: ${MATCH_HISTORY_DIR}`);
  console.log(`  📄 PVPVE matches found: ${pvpveCount}\n`);
});
