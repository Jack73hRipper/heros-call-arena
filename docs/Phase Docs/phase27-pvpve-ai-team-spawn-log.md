# Phase 27 — PVPVE AI Hero Team Spawning (Implementation Log)

**Date:** 2026-03-09
**Phase:** 27 (PVPVE Dungeon Map)
**Sub-phase:** AI Hero Team Spawning Fix

---

## Problem

The Phase 27 PVPVE mode had a UI in the Waiting Room with sliders for:
- **AI Hero Teams** (0 to `teamCount - 1`) — how many corners should be filled with AI-controlled hero parties
- **AI Team Sizes** (1–5 per team) — how many units per AI team

These config values (`pvpve_ai_team_count`, `pvpve_ai_team_sizes`) were:
- Stored and validated in `update_match_config()` ✅
- Sent to the client in config payloads ✅
- **Never actually read to create AI hero units** ❌

When a player started a PVPVE match with AI teams configured, only 1 allied hero (from the generic `ai_allies` slider) appeared near them. The other team corners were empty — no AI hero parties were spawned to fill teams B, C, or D.

## Root Cause

The `_start_pvpve_match()` orchestrator called `_assign_pvpve_teams()` which distributed *existing* units across teams — but no function ever *created* the AI hero units for the non-human team slots. The config values were plumbed through the full stack (client → server config → validation → payload) but the final step of actually spawning units was missing.

## Solution

### New function: `_spawn_pvpve_ai_teams()` (match_manager.py)

Creates AI hero units for PVPVE team slots not occupied by human players.

**Logic:**
1. Reads `pvpve_ai_team_count` and `pvpve_ai_team_sizes` from match config
2. Determines which teams are occupied by humans (humans fill from team A via round-robin)
3. Fills remaining team slots (B, C, D) with AI hero units
4. Each unit gets:
   - `player_id` with `pvpve-ai-{team_key}-{uuid}` prefix (distinguishes from generic `ai-` allies)
   - Random class from `classes_config.json` with stats applied
   - `unit_type="ai"` so the AI system processes their turns
   - `team` set to their designated team key
   - Named after their class (e.g., "Crusader", "Mage 2")
5. Units are registered in `match.ai_ids`, `match.player_ids`, and `_player_states`

### Modified: `_start_pvpve_match()` (match_manager.py)

Added `_spawn_pvpve_ai_teams(match_id)` call as step 0.5, **before** `_assign_pvpve_teams()`. This ensures the AI team units exist in `_player_states` when team distribution runs.

### Modified: `_assign_pvpve_teams()` (match_manager.py)

Updated to recognize `pvpve-ai-` prefixed units as a separate category from generic `ai-` allies:
- `pvpve-ai-` units are placed on their **pre-assigned team** (read from `.team` field)
- Generic `ai-` units continue to be distributed round-robin
- `hero-` units continue to follow their owner
- Humans continue to be distributed round-robin starting with host on team A

### `pvpve-ai-` prefix design choice

A new prefix `pvpve-ai-{team_key}-{uuid}` was chosen instead of reusing `ai-` because:
- Prevents `_assign_pvpve_teams()` from redistributing AI team units away from their assigned team
- `party_manager.is_party_member()` correctly excludes enemy AI teams from human control (only `ai-` prefix on same team is controllable)
- `_clear_ai_units()` still works since it iterates `match.ai_ids` by value, not prefix

## Files Changed

| File | Change |
|------|--------|
| `server/app/core/match_manager.py` | Added `_spawn_pvpve_ai_teams()`, updated `_assign_pvpve_teams()`, wired into `_start_pvpve_match()` |
| `server/tests/test_pvpve_ai_teams.py` | **New** — 22 tests covering AI team spawning, team assignment, and full match integration |

## Test Results

- **22 new tests** — all passing
- **3733 total tests** — all passing (0 regressions)

### New test coverage

| # | Test | Category |
|---|------|----------|
| 1 | No AI units when count is 0 | Spawn |
| 2 | 1 AI team creates correct units | Spawn |
| 3 | 3 AI teams in 4-team match | Spawn |
| 4 | Units have correct team assignment | Spawn |
| 5 | Units are AI type and ready | Spawn |
| 6 | Units have class stats (HP > 0) | Spawn |
| 7 | Units tracked in ai_ids | Spawn |
| 8 | Units tracked in player_ids | Spawn |
| 9 | Varying team sizes respected | Spawn |
| 10 | Default team size = 3 | Spawn |
| 11 | Team size clamped to max 5 | Spawn |
| 12 | Team size clamped to min 1 | Spawn |
| 13 | AI teams skip human-occupied teams | Spawn |
| 14 | AI units on correct team after assign | Assignment |
| 15 | Human still on team A with AI teams | Assignment |
| 16 | Generic AI allies coexist with AI teams | Assignment |
| 17 | Full match starts with AI teams | Integration |
| 18 | All 4 teams populated after start | Integration |
| 19 | AI units have valid positions | Integration |
| 20 | 2-team match with 1 AI team | Integration |
| 21 | PVE enemies still spawn alongside | Integration |
| 22 | AI teams not in team_pve | Integration |

---

## Follow-up Fix: AI Allies Staying on Owner's Team

### Problem

After the initial fix, in-game testing revealed that AI allies from the "AI Teammates" slider (`ai_allies` config) were being distributed **round-robin across all active teams** instead of staying on the human player's team (team A).

Example: In a 4-team PVPVE match with `ai_allies=4`, each of the 4 teams got 1 AI ally — the human ended up with only 1 ally instead of 4. The WaitingRoom UI label says "Add AI allies to your own team," so the intent was always to keep them on team A.

### Root Cause

In `_assign_pvpve_teams()`, generic `ai-` allies were distributed with:
```python
assigned_team = active_teams[i % team_count]
```
This round-robin logic scattered allies across all teams equally.

### Fix

Changed the generic `ai-` distribution to always assign team `"a"`:
```python
assigned_team = "a"
```

### Test Update

Renamed `test_ai_allies_distributed_across_teams` → `test_ai_allies_stay_on_owner_team` and updated assertions to verify all allies land on team A.

### Test Results

- **3733 total tests** — all passing (1 pre-existing flaky test: `test_adjacent_attack_deals_damage` occasionally fails on random crit rolls, unrelated)

## How It Works Now

1. Player configures PVPVE in Waiting Room: 4 teams, 3 AI hero teams, 3 units each
2. Match starts → `_start_pvpve_match()` runs
3. `_spawn_pvpve_ai_teams()` creates 9 AI hero units (3×3) on teams B, C, D
4. `_assign_pvpve_teams()` distributes: human → A, pvpve-ai → B/C/D
5. Dungeon generates with 4 corner spawn zones
6. Smart spawns place each team in their corner formation
7. PVE enemies populate the dungeon rooms
8. All 4 teams play — AI teams behave like any other AI units
9. Last team standing wins
