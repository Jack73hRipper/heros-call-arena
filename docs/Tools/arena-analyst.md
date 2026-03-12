# Arena Analyst — Match Tracker & Balance Tool

> **Status:** Phase D complete (Advanced Views — CompAnalysis with ranked best/worst comps + sortable/filterable comp table, Timeline Replay with SVG damage curves + death markers + turn-by-turn event scrubber + event type filters, TrendCharts with summary cards + match volume bars + avg match length line chart + damage creep chart + stacked win rate distribution + class win rate overview) · Phase C complete (Core Views — MatchList with filter bar, MatchDetail with scoreboard/team comparison/MVP card/kill feed, ClassBalance with sortable win rate table/stat charts/class-vs-class matrix, grimdark CSS theme, 3606 tests passing)
> **Purpose:** Standalone tool that captures, persists, and visualizes PvP (and PvE) match data for balance analysis, composition tracking, and trend discovery.

---

## Table of Contents

1. [Overview](#1-overview)
2. [Goals](#2-goals)
3. [Architecture](#3-architecture)
4. [Data Collection (Server-Side)](#4-data-collection-server-side)
5. [Match Report Schema](#5-match-report-schema)
6. [Arena Analyst Tool (Frontend)](#6-arena-analyst-tool-frontend)
7. [Implementation Plan](#7-implementation-plan)
8. [File Map](#8-file-map)

---

## 1. Overview

Currently all combat statistics (damage dealt/taken, healing, kills, per-skill breakdowns) are tracked live during matches but **discarded when the match ends**. The Arena Analyst adds:

1. **Persistent match reports** — a JSON file written at match end containing full combat data
2. **Standalone viewer tool** — a React+Vite app (like Enemy Forge) for browsing, filtering, and analyzing match history outside the game

This is primarily aimed at **PvP 5v5** balance tuning (AI vs AI, Player vs AI, mixed), but captures all match types for completeness.

---

## 2. Goals

| Goal | Description |
|------|-------------|
| **Match History** | Browse all past matches chronologically with filters (match type, map, date) |
| **Match Scoreboard** | Deep-dive into any single match — per-unit stats, team comparison, kill timeline |
| **Class Balance** | Aggregate win rates, average damage/healing/kills per class across many matches |
| **Composition Tracking** | Which team comps (e.g. 2 Crusader + 1 Confessor + 1 Ranger + 1 Mage) win most |
| **Timeline Replay** | Turn-by-turn event log for a single match — see damage curves and fight flow |
| **Trend Charts** | Track shifts over time as balance changes are made |
| **Zero game impact** | Data collection is a single JSON write at match end — no gameplay perf cost |
| **Outside the game** | Separate tool on its own port, no coupling to client UI |

---

## 3. Architecture

```
┌──────────────────────────────┐
│     Game Server (FastAPI)    │
│                              │
│  tick_loop.py                │
│    └─ match ends             │
│       └─ save_match_report() │  ← NEW: writes JSON to disk
│          └─ server/data/     │
│             match_history/   │
│               ├─ 2026-03-08_abc123.json
│               ├─ 2026-03-08_def456.json
│               └─ ...         │
└──────────────────────────────┘

┌──────────────────────────────┐
│   Arena Analyst Tool         │
│   (standalone, separate port)│
│                              │
│   Express server.js (:5240)  │   ← reads match_history/ folder
│     /api/matches             │   ← list + filter matches
│     /api/matches/:id         │   ← single match detail
│     /api/class-stats         │   ← aggregate class balance
│     /api/comp-stats          │   ← composition win rates
│     /api/trends              │   ← time-series data
│                              │
│   Vite React app (:5241)     │   ← visual dashboard
│     Match History list       │
│     Match Detail scoreboard  │
│     Class Balance dashboard  │
│     Composition Analysis     │
│     Timeline Replay          │
│     Trend Charts             │
└──────────────────────────────┘
```

---

## 4. Data Collection (Server-Side)

### 4.1 What Already Exists

The following data is already tracked in memory during a match:

| Source | Location | Data |
|--------|----------|------|
| `_combat_stats` | `hero_manager.py` | Per-unit: damage_dealt, damage_taken, healing_done, items_looted, turns_survived |
| `_kill_tracker` | `hero_manager.py` | Per-unit: enemy_kills, boss_kills |
| `_player_states` | `match_manager.py` | Full PlayerState: class_id, team, hp, position, buffs, equipment, is_alive |
| `_active_matches` | `match_manager.py` | MatchState: config (map, match_type, teams), turn count, team rosters |
| `ActionResult` | `actions.py` | Per-action: damage_dealt, heal_amount, skill_id, killed, is_crit, target_id |
| `TurnResult` | `actions.py` | Per-turn: all actions, deaths, winner, elite_kills |

### 4.2 New: `save_match_report()`

A single new function in `hero_manager.py` that serializes the above into a JSON file.

**Called from:** `tick_loop.py`, right before `end_match(match_id)` in the match-end block.

**Writes to:** `server/data/match_history/{timestamp}_{match_id}.json`

### 4.3 New: Per-Turn Event Log

To enable timeline replay, we also need a lightweight **per-turn event buffer** that accumulates during the match. Each tick appends a compact summary:

```python
# Stored in _match_timeline: dict[str, list[dict]]
# Each entry: {
#   "turn": 5,
#   "events": [
#     {"type": "damage", "src": "player_1", "tgt": "ai_3", "dmg": 22, "skill": "auto_attack", "crit": false},
#     {"type": "heal", "src": "player_2", "tgt": "player_1", "amt": 15, "skill": "heal"},
#     {"type": "death", "unit": "ai_3", "killer": "player_1"},
#     {"type": "buff", "src": "player_2", "tgt": "player_1", "buff": "war_cry"},
#   ]
# }
```

This is appended in `tick_loop.py` after `resolve_turn()`, using data already in `turn_result.actions`.

---

## 5. Match Report Schema

Each match report JSON file contains:

```jsonc
{
  // ── Match metadata ──
  "match_id": "abc123",
  "timestamp": "2026-03-08T21:30:00Z",
  "duration_turns": 47,
  "map_id": "open_arena",
  "match_type": "pvp",           // pvp | solo_pve | mixed | dungeon
  "winner": "team_a",            // team_a | team_b | draw | player_id | party_wipe
  "config": {
    "max_players": 10,
    "tick_rate": 1.0,
    "ai_opponents": 5,
    "ai_allies": 0,
    "ai_opponent_classes": ["crusader", "confessor", "ranger", "inquisitor", "hexblade"],
    "ai_ally_classes": []
  },

  // ── Team rosters ──
  "teams": {
    "team_a": [
      {
        "unit_id": "player_1",
        "username": "Hero_One",
        "class_id": "crusader",
        "team": "a",
        "is_ai": false,
        "base_hp": 150,
        "base_melee_damage": 20,
        "base_armor": 8
      }
      // ... more units
    ],
    "team_b": [ /* ... */ ]
  },

  // ── Per-unit combat stats (end-of-match totals) ──
  "unit_stats": {
    "player_1": {
      "unit_id": "player_1",
      "username": "Hero_One",
      "class_id": "crusader",
      "team": "a",
      "is_ai": false,
      "status": "survived",        // survived | died
      "damage_dealt": 487,
      "damage_taken": 312,
      "healing_done": 0,
      "kills": 3,
      "boss_kills": 0,
      "deaths": 0,
      "turns_survived": 47,
      "items_looted": 0,
      "highest_hit": 42,
      "overkill_damage": 15
    }
    // ... all units (both teams)
  },

  // ── Turn-by-turn timeline ──
  "timeline": [
    {
      "turn": 1,
      "events": [
        { "type": "move", "unit": "player_1", "to": [5, 3] },
        { "type": "damage", "src": "player_3", "tgt": "ai_2", "dmg": 12, "skill": "auto_attack", "crit": false },
        { "type": "heal", "src": "player_2", "tgt": "player_1", "amt": 15, "skill": "heal" }
      ]
    },
    {
      "turn": 2,
      "events": [
        { "type": "damage", "src": "ai_1", "tgt": "player_4", "dmg": 18, "skill": "auto_attack", "crit": false },
        { "type": "death", "unit": "ai_5", "killer": "player_1" }
      ]
    }
    // ... one entry per turn
  ],

  // ── Summary / derived (computed at write time) ──
  "summary": {
    "team_a_total_damage": 1843,
    "team_b_total_damage": 1201,
    "team_a_total_healing": 340,
    "team_b_total_healing": 0,
    "team_a_kills": 5,
    "team_b_kills": 2,
    "team_a_deaths": 2,
    "team_b_deaths": 5,
    "first_blood_turn": 4,
    "first_blood_killer": "player_3",
    "first_blood_victim": "ai_2",
    "mvp": "player_1",              // highest damage + kills composite
    "mvp_damage": 487,
    "mvp_kills": 3
  }
}
```

---

## 6. Arena Analyst Tool (Frontend)

### 6.1 Technology

Same stack as all existing tools:
- **React 18** + **Vite 5** for the frontend
- **Express** micro-server for file I/O (reads `server/data/match_history/`)
- Grimdark CSS theme matching the game's visual style
- No external charting library initially — use CSS bars (like CombatMeter) and canvas for charts; can add a lightweight lib later if needed

### 6.2 Tabs

#### Tab 1: Match History
- Scrollable table of all matches, newest first
- Columns: Date, Map, Type, Teams (class icons), Winner, Duration (turns), MVP
- Filter controls: match type dropdown, map dropdown, date range, class filter
- Click a row → opens Match Detail

#### Tab 2: Match Detail
- **Header:** Match metadata (map, type, duration, winner banner)
- **Scoreboard:** Two-column team layout, per-unit stat rows with horizontal bars (damage, healing, kills) — similar to existing CombatMeter UI
- **Kill Feed:** Chronological list of kills with timestamps (turn numbers)
- **MVP Card:** Highlighted stat card for highest-performing unit
- **Team Comparison:** Side-by-side aggregate bars (total damage, total healing, total kills)

#### Tab 3: Class Balance
- **Win Rate Table:** Class → matches played, wins, losses, win rate %
- **Stat Averages:** Class → avg damage/healing/kills/deaths per match
- **Class vs Class Matrix:** Heatmap grid — when Class A faces Class B, who wins more?
- Filterable by match type and date range

#### Tab 4: Composition Analysis
- **Comp Win Rates:** Group matches by team composition (sorted set of class IDs), show win/loss record
- **Best/Worst Comps:** Top 5 and bottom 5 compositions by win rate (min 3 matches)
- **Comp vs Comp:** If enough data, show head-to-head records between specific compositions

#### Tab 5: Timeline Replay
- Select a match from history
- Visual turn-by-turn timeline: horizontal axis = turns, vertical = events
- Damage curve chart: cumulative damage per team over time
- Death markers on the timeline
- HP estimation per unit over time (derived from damage_taken events)

#### Tab 6: Trends
- **Match Volume:** Matches per day/week
- **Win Rate Drift:** Class win rates over time (detect if a balance change shifted things)
- **Average Match Length:** Over time
- **Damage Creep:** Average team damage per match over time

### 6.3 Express API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/matches` | List all match reports (summary only: id, date, map, type, winner, duration). Supports query params: `?type=pvp&map=open_arena&from=2026-03-01&to=2026-03-08` |
| GET | `/api/matches/:id` | Full match report JSON for a single match |
| GET | `/api/class-stats` | Aggregated class balance data (computed from all reports on the fly or cached) |
| GET | `/api/comp-stats` | Composition win rate data |
| GET | `/api/trends` | Time-series aggregates for trend charts |
| DELETE | `/api/matches/:id` | Delete a single match report |
| POST | `/api/matches/clear` | Clear all match history (with confirmation) |

---

## 7. Implementation Plan

### Phase A: Data Collection (Server-Side) — 2 steps ✅

| Step | Task | Files | Description |
|------|------|-------|-------------|
| **A1** ✅ | Per-turn timeline buffer | `hero_manager.py`, `match_manager.py`, `tick_loop.py` | Added `_match_timeline` dict to `match_manager.py`, `record_turn_events()` function to `hero_manager.py`. Called after `resolve_turn()` each tick to append compact event summaries (damage, heal, move, death, buff, elite_kill). |
| **A2** ✅ | Match report writer | `hero_manager.py`, `tick_loop.py` | Added `save_match_report()` function that serializes all match data + timeline to `server/data/match_history/{timestamp}_{match_id}.json`. Called from `tick_loop.py` right before `end_match()`. Created `server/data/match_history/` directory. |

### Phase B: Tool Scaffold — 3 steps ✅

| Step | Task | Files | Description |
|------|------|-------|-------------|
| **B1** ✅ | Project setup | `tools/arena-analyst/package.json`, `vite.config.js`, `index.html`, `src/main.jsx`, `src/App.jsx`, `src/styles/main.css` | Scaffolded React+Vite project with tab navigation shell (6 tabs), match history table with click-to-detail, grimdark CSS theme. Vite on port 5240, Express proxy on 5241. |
| **B2** ✅ | Express API server | `tools/arena-analyst/server.js` | Implemented 7 endpoints: GET `/api/matches` (with type/map/from/to filters), GET `/api/matches/:id`, DELETE `/api/matches/:id`, POST `/api/matches/clear`, GET `/api/class-stats` (win rates, avg damage/healing/kills/deaths), GET `/api/comp-stats` (composition win rates), GET `/api/trends` (daily aggregates). Reads from `server/data/match_history/`. |
| **B3** ✅ | Batch file + README update | `start-arena-analyst.bat`, `README.md`, `tools/package.json` | Added launch script, registered in workspace `workspaces` array, added to README project structure (bat file, tools dir, docs/Tools), added to Tools documentation list, updated current status. |

### Phase C: Core Views — 3 steps ✅

| Step | Task | Files | Description |
|------|------|-------|-------------|
| **C1** ✅ | Match History tab with filters | `App.jsx`, `components/MatchList.jsx`, `styles/main.css` | Extracted MatchList component with full filter bar (type dropdown, map dropdown, date range, search text), client-side filtering, match count display, score column (team_a_kills – team_b_kills), type badges with colored backgrounds, formatted dates, clear filters button. Refactored App.jsx to import MatchList, MatchDetail, ClassBalance components. |
| **C2** ✅ | Match Detail scoreboard | `components/MatchDetail.jsx`, `styles/main.css` | Full match detail view: header with back button and match metadata, team comparison bars (damage/healing/kills with proportional A-vs-B fills), MVP card with gold accent border and stats, per-team scoreboards with inline stat bars (damage/healing proportional to match max), class color tags, AI badges, survived/died status tags, kill feed extracted from timeline events. |
| **C3** ✅ | Class Balance dashboard | `components/ClassBalance.jsx`, `styles/main.css` | Sortable win rate table (click column headers to sort asc/desc) with win rate bars (green >55%, red <45%, centered 50% marker), stat averages comparison section (4 horizontal bar charts: avg damage, healing, kills, deaths), collapsible class-vs-class matrix (on-demand fetch of all match details, computes pairwise win rates with color-coded cells and W-L records). |

### Phase D: Advanced Views — 3 steps ✅

| Step | Task | Files | Description |
|------|------|-------|-------------|
| **D1** ✅ | Composition Analysis tab | `CompAnalysis.jsx`, `styles/main.css` | Full composition analysis view: best/worst compositions panels (ranked cards with win rate, W-L record, min 3 matches), sortable/filterable composition table (sort by matches/win rate/W/L, filter by min matches and team size), class tags with color-coded borders, win rate bars integrated from ClassBalance pattern. Reads from `/api/comp-stats` endpoint. |
| **D2** ✅ | Timeline Replay tab | `Timeline.jsx`, `styles/main.css` | Turn-by-turn timeline replay: match selector dropdown, match summary banner, SVG cumulative damage curves (Team A vs Team B with death marker vertical lines and selected-turn indicator), clickable turn strip bar chart (bar height = event count, red bars for death turns, gold accent for selected), event type filter buttons (damage/heal/death/buff/elite_kill), detailed event viewer per turn (formatted descriptions with unit names, damage values, skill names, crit badges), death timeline with turn badges and colored unit names. |
| **D3** ✅ | Trend Charts tab | `TrendCharts.jsx`, `styles/main.css` | Time-series trend dashboard: summary cards (total matches, active days, avg/day, avg turns, avg damage), match volume per day bar chart, average match length line chart (SVG with area fill + grid lines + dots), damage creep line chart (same pattern, red-themed), stacked win rate distribution per day (Team A/B/Draw segments), current class win rate horizontal bars (with 50% midline marker and W-L records). Fetches from `/api/trends`, `/api/class-stats`, and `/api/matches` in parallel. |

### Phase E: Polish — 2 steps

| Step | Task | Description |
|------|------|-------------|
| **E1** | Testing | Run multiple PvP matches to generate data, verify all views display correctly. |
| **E2** | Quality of life | Export to CSV, print-friendly view, comparison mode (select 2 matches to compare side-by-side). |

---

## 8. File Map

### Server Changes (minimal)

| File | Change |
|------|--------|
| `server/app/core/hero_manager.py` | Add `_match_timeline` dict, `record_turn_events()`, `save_match_report()` |
| `server/app/services/tick_loop.py` | Call `record_turn_events()` after resolve_turn, call `save_match_report()` before end_match |
| `server/data/match_history/` | New directory for match report JSON files |

### New Tool

```
tools/arena-analyst/
├── package.json
├── vite.config.js
├── index.html
├── server.js                    # Express API (port 5240)
├── src/
│   ├── main.jsx
│   ├── App.jsx                  # Tab navigation + data fetching
│   ├── components/
│   │   ├── MatchList.jsx        # Tab 1: Match History
│   │   ├── MatchDetail.jsx      # Tab 2: Match Scoreboard
│   │   ├── ClassBalance.jsx     # Tab 3: Class Balance
│   │   ├── CompAnalysis.jsx     # Tab 4: Composition Analysis
│   │   ├── Timeline.jsx         # Tab 5: Timeline Replay
│   │   └── TrendCharts.jsx      # Tab 6: Trend Charts
│   └── styles/
│       └── main.css             # Grimdark theme
├── start-arena-analyst.bat      # Launch script (root level)
```

### Root Level

| File | Change |
|------|--------|
| `start-arena-analyst.bat` | New launch script |
| `README.md` | Add Arena Analyst to tool list, project structure, and docs section |
