# PVPVE Analyst — 4-Team Dungeon Match Inspector

> **Status:** Phase A complete (Full 6-tab dashboard — Match Browser, 4-Team Scoreboard, Combat Timeline, Exploration Inspector, Equipment Report, Batch Overview)
> **Purpose:** Standalone visual tool for inspecting PVPVE batch simulation data — 4-team dungeon matches with PVE enemies, exploration tracking, and equipment flow.

---

## Table of Contents

1. [Overview](#1-overview)
2. [Goals](#2-goals)
3. [Architecture](#3-architecture)
4. [Data Source](#4-data-source)
5. [Tabs & Features](#5-tabs--features)
6. [Running the Tool](#6-running-the-tool)
7. [File Map](#7-file-map)
8. [Future Development & QoL](#8-future-development--qol)

---

## 1. Overview

The PVPVE batch simulator (`server/batch_pvpve.py`) generates detailed match reports for 4-team dungeon games where human-controlled-style AI teams compete against each other **and** PVE enemies. These matches produce rich data — tile exploration, equipment management, team combat, boss encounters — but the CLI output (ASCII maps, scrolling text) is hard to analyze at scale.

The **PVPVE Analyst** is a standalone React + Express dashboard that reads the JSON match reports and provides:

- **Individual match deep-dives** — scoreboard, timeline, exploration health, equipment loadouts
- **Aggregate analysis** — win rates, class performance, team balance, daily trends
- **Visual charts** — survival curves, damage charts, pie charts, color-coded stat bars

This tool is designed for **developer use** — quick visual inspection of PVPVE data without parsing terminal output.

---

## 2. Goals

| Goal | Description |
|------|-------------|
| **Match Browsing** | Filter and search PVPVE matches by winner, hero name, match ID |
| **4-Team Scoreboard** | Per-team stats with color-coded badges (A=blue, B=red, C=yellow, D=magenta) |
| **Combat Timeline** | Canvas-drawn survival curves, cumulative damage, kill feed |
| **Exploration Health** | Tile coverage, move efficiency, oscillation detection, health scores |
| **Equipment Tracking** | Item economy, per-hero loadouts, rarity-colored item names |
| **Batch Aggregates** | Win rate distribution, class performance table, team aggregate stats |
| **Zero game impact** | Reads JSON files from disk only — no connection to game server |
| **Outside the game** | Separate tool on its own port, follows Arena Analyst architectural pattern |

---

## 3. Architecture

```
┌──────────────────────────────────────────┐
│  Batch Simulator (CLI)                   │
│                                          │
│  server/batch_pvpve.py                   │
│    └─ run_headless_pvpve()               │
│       └─ saves JSON to                   │
│          server/data/match_history/      │
│            ├─ pvpve_20260308_abc123.json │
│            ├─ pvpve_20260308_def456.json │
│            └─ ...                        │
└──────────────────────────────────────────┘

┌──────────────────────────────────────────┐
│  PVPVE Analyst Tool                      │
│  (standalone, separate port)             │
│                                          │
│  Express server.js  (:5242)              │  ← reads match_history/
│    GET /api/matches                      │  ← list PVPVE matches
│    GET /api/matches/:id                  │  ← single match detail
│    GET /api/matches/:id/timeline         │  ← timeline events only
│    GET /api/team-stats                   │  ← aggregate team data
│    GET /api/class-stats                  │  ← per-class performance
│    GET /api/batch-overview               │  ← win counts, daily data
│                                          │
│  Vite React app     (:5243)              │  ← visual dashboard
│    Tab 1: Match Browser                  │
│    Tab 2: 4-Team Scoreboard              │
│    Tab 3: Combat Timeline                │
│    Tab 4: Exploration Inspector          │
│    Tab 5: Equipment Report               │
│    Tab 6: Batch Overview                 │
└──────────────────────────────────────────┘
```

---

## 4. Data Source

Match reports are JSON files in `server/data/match_history/` filtered by `match_type === "pvpve"`.

### Match Report Schema

| Field | Type | Description |
|-------|------|-------------|
| `match_id` | string | Unique match identifier |
| `timestamp` | string | ISO timestamp |
| `duration_turns` | number | Total turns in the match |
| `map_id` | string | Map identifier |
| `match_type` | string | Always `"pvpve"` for this tool |
| `winner` | string | `a`, `b`, `c`, `d`, `team_a`–`team_d`, or `draw` |
| `teams` | object | `{ team_a: [...], team_b: [...], team_c: [...], team_d: [...] }` |
| `unit_stats` | object | Per-unit: damage, healing, kills, deaths, items, boss_kills, etc. |
| `timeline` | array | `[{ turn, events: [{ type, ... }] }]` |
| `summary` | object | Aggregate team totals, MVP, first blood |

### Unit Stat Fields

`username`, `class_id`, `team`, `status`, `damage_dealt`, `damage_taken`, `healing_done`, `kills`, `boss_kills`, `deaths`, `turns_survived`, `items_looted`, `highest_hit`, `overkill_damage`

---

## 5. Tabs & Features

### Tab 1: Match Browser
- Filterable list of all PVPVE matches
- Filter by winner team, search by hero name or match ID
- Table columns: date, match ID, winner, turns, hero count, PVE count, MVP, per-team kills
- Click a match to open the 4-Team Scoreboard

### Tab 2: 4-Team Scoreboard
- Match info header: winner, total turns, MVP, first blood, PVE enemy count
- Comparative stat bars: total damage and healing per team
- 4 team summary cards: alive/total, kills, deaths, damage, healing, items, boss kills
- Per-team hero roster: hero, class, status, damage, healing, kills, deaths, turns, items, highest hit
- PVE enemy summary grouped by class

### Tab 3: Combat Timeline
- Canvas-drawn survival curve: 4 colored lines showing alive count per turn
- Canvas-drawn cumulative damage chart per team
- Kill feed event log with team-colored entries (damage, death, heal, skill events)
- Top 20 highest-damage turns

### Tab 4: Exploration Inspector
- Per-team exploration cards with health scores (0–100)
- Tile coverage bars, total moves, move efficiency
- Per-hero movement summary table
- Exploration health diagnosis: detects low coverage, stalling, poor efficiency

### Tab 5: Equipment Report
- Item economy overview: items looted, equipped, potions used
- Items looted per team comparative bars
- Per-team equipment roster: hero, class, weapon, armor, accessory, HP, ATK, DEF
- Hero performance & loot table with rarity-colored item names

### Tab 6: Batch Overview
- Summary cards: total matches, average turns, draw rate
- Win rate pie chart (canvas-drawn) with legend
- Team win rate bars
- Team aggregate stats table: wins, win rate, damage, healing, kills, deaths, survival rate
- Class performance table: appearances, win rate, survival, avg stats, boss kills
- Daily match activity table

---

## 6. Running the Tool

```
start-pvpve-analyst.bat
```

This will:
1. Install npm dependencies (shared `tools/package.json`)
2. Start the Express API server on **port 5242**
3. Start the Vite dev server on **port 5243**

Open `http://localhost:5243` in a browser.

### Prerequisites
- Node.js 18+
- PVPVE match data in `server/data/match_history/` (run `start-batch-pvpve.bat` first)

---

## 7. File Map

```
tools/pvpve-analyst/
├── server.js                     # Express API (port 5242)
├── package.json                  # Dependencies (react 18, vite 5, express 4)
├── vite.config.js                # Vite config (port 5243, proxy /api → 5242)
├── index.html                    # HTML entry point
└── src/
    ├── main.jsx                  # React root mount
    ├── App.jsx                   # Tab router + match state management
    ├── styles/
    │   └── main.css              # Grimdark theme + 4-team color system
    └── components/
        ├── MatchBrowser.jsx      # Tab 1: filterable match list
        ├── TeamScoreboard.jsx    # Tab 2: 4-team detailed scoreboard
        ├── CombatTimeline.jsx    # Tab 3: canvas charts + kill feed
        ├── ExplorationInspector.jsx  # Tab 4: exploration health
        ├── EquipmentReport.jsx   # Tab 5: equipment & loot data
        └── BatchOverview.jsx     # Tab 6: aggregate stats & charts

start-pvpve-analyst.bat           # Launcher script (root)
docs/Tools/pvpve-analyst.md       # This documentation
```

---

## 8. Future Development & QoL

### Phase B — Enhanced Visuals
| Feature | Description |
|---------|-------------|
| **ASCII Map Renderer** | Render the dungeon grid in-browser using canvas — show team positions, walls, doors, loot tiles, PVE spawn locations |
| **Turn-by-Turn Replay** | Step through each turn with animated unit movement on the map, damage numbers floating, death markers |
| **Heatmaps** | Overlay tile visit frequency per team on the dungeon grid — identify exploration patterns and dead zones |
| **Damage Breakdown Tooltips** | Hover over any damage number to see skill-by-skill breakdown per turn |

### Phase C — Advanced Analysis
| Feature | Description |
|---------|-------------|
| **Oscillation Detector** | Visual indicator for teams stuck in movement oscillation patterns — highlight problematic turns |
| **Door Interaction Timeline** | Show when teams open/close/block doors, visualize chokepoint control |
| **Boss Fight Breakdown** | Dedicated panel for PVE boss encounters — HP curves, DPS uptime, team coordination score |
| **Team Composition Analysis** | Which class combinations perform best in PVPVE — win rates by comp, synergy scores |
| **Equipment Upgrade Flow** | Sankey diagram showing item flow: spawn gear → looted items → final loadout per hero |

### Phase D — Comparison & Export
| Feature | Description |
|---------|-------------|
| **Match Comparison** | Side-by-side comparison of two matches — highlight differences in team performance |
| **Batch Comparison** | Compare two batch runs (e.g., before/after a balance change) — delta charts for win rates, class performance |
| **CSV/JSON Export** | Export filtered data sets for external analysis (spreadsheets, Python notebooks) |
| **Match Bookmarking** | Tag interesting matches with notes for later review |
| **Auto-Refresh** | Watch the match_history folder for new files and auto-update the dashboard during batch runs |

### Phase E — Quality of Life
| Feature | Description |
|---------|-------------|
| **Keyboard Navigation** | Arrow keys to browse matches, Tab to switch panels, Enter to open detail |
| **URL Routing** | Deep-link to specific matches/tabs via URL hash — shareable links |
| **Dark/Light Theme Toggle** | Light mode option for readability in bright environments |
| **Match Search History** | Remember recent searches and filters across sessions |
| **Responsive Layout** | Adapt layout for narrower screens — collapsible panels, mobile-friendly tables |
| **Performance Optimization** | Virtual scrolling for large match lists, lazy-load timeline data, memoized chart renders |
