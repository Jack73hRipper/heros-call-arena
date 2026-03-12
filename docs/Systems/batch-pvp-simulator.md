# Batch PvP Simulator

Headless 5v5 match runner for class balance testing. Runs real matches without a browser — same game logic, same maps, same AI, same combat — just no WebSocket broadcasting.

**Files:**
- `server/batch_pvp.py` — simulator script
- `start-batch-pvp.bat` — double-click launcher

## Why the Data Is Accurate

The simulator calls the exact same server functions as a live match:

| System | Function | Same as Live? |
|---|---|---|
| Map geometry & obstacles | `load_map()`, `get_obstacles_with_door_states()` | Yes |
| FOV + shared team vision | `compute_fov()`, `get_team_fov()` | Yes |
| AI decisions | `run_ai_decisions()` (A* pathfinding, skill usage, targeting, stances, memory) | Yes |
| Turn resolution | `resolve_turn()` (movement, melee, ranged, skills, buffs, DoTs, deaths) | Yes |
| Combat stats tracking | `track_damage_dealt()`, `track_healing_done()`, etc. | Yes |
| Timeline recording | `record_turn_events()` | Yes |
| Match reports | `save_match_report()` → JSON to `server/data/match_history/` | Yes |
| WebSocket broadcasts | FOV-filtered payloads to browser clients | **Skipped** |

The WebSocket broadcasts are purely presentational — they send data to the screen but have zero effect on game state, AI decisions, or combat outcomes. Skipping them is equivalent to running a match with no spectators.

## How It Works

1. Creates a match via `create_match()` with all AI units and a dummy host
2. Calls `start_match()` (resolves spawns, applies class stats)
3. Removes the dummy host from match state
4. Runs a synchronous tick loop:
   - Computes FOV for all units
   - Runs AI decisions with shared team vision
   - Resolves the turn (combat, movement, skills, buffs, deaths)
   - Tracks combat stats and timeline events
   - Checks for winner
5. Saves the match report via `save_match_report()` on completion
6. Cleans up in-memory state

Reports land in `server/data/match_history/` in the same JSON format as live matches. Arena Analyst reads them immediately.

## Usage

```bash
cd server

# Basic: 10 random matches
python batch_pvp.py

# Specific team comps
python batch_pvp.py --matches 50 \
  --team-a crusader,confessor,ranger,hexblade,mage \
  --team-b blood_knight,bard,inquisitor,revenant,shaman

# Random comps (broad class balance sampling)
python batch_pvp.py --matches 100 --randomize

# Mirror mode (same comp both sides — tests map balance)
python batch_pvp.py --matches 30 --mirror

# Round-robin (every comp vs every comp, sampled)
python batch_pvp.py --round-robin --matches 200

# Different map
python batch_pvp.py --matches 20 --map open_arena --randomize

# List available classes and maps
python batch_pvp.py --list-classes
python batch_pvp.py --list-maps
```

Or use the batch file: `start-batch-pvp.bat` (passes arguments through).

## CLI Options

| Flag | Description | Default |
|---|---|---|
| `--matches N` | Number of matches to run | 10 |
| `--map MAP_ID` | Map to fight on | `open_arena_large` |
| `--team-a CLASSES` | Comma-separated class IDs for Team A | Random |
| `--team-b CLASSES` | Comma-separated class IDs for Team B | Random |
| `--max-turns N` | Turn limit before declaring a draw | 200 |
| `--randomize` | Random comps each match | — |
| `--mirror` | Both teams use the same random comp | — |
| `--round-robin` | Every possible 5v5 comp pairing | — |
| `--list-classes` | Print available class IDs and exit | — |
| `--list-maps` | Print available map IDs and exit | — |

## Available Classes (11)

`bard`, `blood_knight`, `confessor`, `crusader`, `hexblade`, `inquisitor`, `mage`, `plague_doctor`, `ranger`, `revenant`, `shaman`

## Performance

~0.2 seconds per match. 100 matches completes in ~20 seconds.

## Viewing Results

Open Arena Analyst (`start-arena-analyst.bat`). All batch matches appear alongside live matches in every view:

- **MatchList** — filterable match history
- **MatchDetail** — scoreboard, team comparison, MVP, kill feed
- **ClassBalance** — win rates, stat averages, class-vs-class matrix
- **CompAnalysis** — best/worst team compositions
- **Timeline** — SVG damage curves, death markers, turn-by-turn events
- **TrendCharts** — match volume, damage creep, win distribution

## Console Output

The simulator prints a live progress table and summary:

```
======================================================================
  BATCH PVP RESULTS — 20 matches on open_arena_large
======================================================================
  Team A wins:   14  (70.0%)
  Team B wins:    6  (30.0%)
  Draws:          0  (0.0%)
  Avg turns:   39.5

  Class             Games   Wins Losses    Win%
  ---------------- ------ ------ ------ -------
  hexblade             13      9      4   69.2%
  blood_knight         14      9      5   64.3%
  shaman               23     13     10   56.5%
  confessor            16      9      7   56.2%
  ranger               20     11      9   55.0%
  crusader             21     11     10   52.4%
  revenant             22     11     11   50.0%
  bard                 19      9     10   47.4%
  inquisitor           16      6     10   37.5%
  mage                 19      7     12   36.8%
  plague_doctor        17      5     12   29.4%
======================================================================
```
