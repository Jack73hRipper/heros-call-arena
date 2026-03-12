# Phase 3: Arena Refined — Design Document

## Overview

**Goal:** Larger maps for 6-8 players and intelligent spawn systems.

**Timeline:** 3-4 weeks  
**Status:** In Progress  
**Prerequisites:** Phase 2.1 complete

---

## Phase 2.1 Results

**Core gameplay validated. Ready to scale.**

Issues to address:
- 15x15 maps feel cramped with 8 players
- Players sometimes spawn on same tile
- No team formation logic

---

## Phase 3 Scope

**Focus:** Map scaling and spawn system refinement only.

**Not included:** Unit types, skills, loot, progression, new game modes, or themes.

---

## Feature 1: Larger Map Variants ✅ Complete

**Problem:** 15x15 maps feel cramped with 8 players.

**Solution:** Create additional maps at larger sizes for testing.

**Map Sizes Created:**

- **12x12** - Small (2-4 players)
- **15x15** - Medium (existing size, kept current maps)
- **20x20** - Large (6-8 players)
- **25x25** - Extra Large (testing scalability limits)

**New Maps Delivered:**

| Map | Size | Status |
|-----|------|--------|
| Open Arena Small | 12×12 | ✅ Complete |
| Open Arena Large | 20×20 | ✅ Complete |
| Maze Large | 20×20 | ✅ Complete |
| Islands Large | 20×20 | ✅ Complete |
| Test Map XL | 25×25 | ✅ Complete |

**Also Completed:**
- Lobby map selector with size labels
- Variable grid size support (canvas adapts to any map dimension)
- All maps maintain original obstacle density percentages

---

## Feature 2: Smart Spawn System ✅ Complete

**Problem:** Players spawn on same tile, no team formation logic.

**Solution:** Team-aware spawn system with proper spacing.

### Implementation

New module: `server/app/core/spawn.py` — Pure spawn logic, no framework dependencies.

| Function | Purpose |
|----------|---------|
| `assign_spawns()` | Top-level orchestrator — detects FFA vs team mode, delegates |
| `compute_team_spawns()` | Places teammates in compact BFS formations within zone |
| `compute_ffa_spawns()` | Greedy max-distance placement across FFA points |
| `validate_spawn()` | Checks walkable, in-bounds, unoccupied |
| `find_nearest_valid()` | BFS fallback to nearest valid tile |

### Team-Based Spawning ✅

- Teammates spawn in **compact formations** (BFS growth, Chebyshev ≤ 2)
- Different teams spawn in **opposite corner zones**
- Minimum **5+ tiles** between opposing team zones on all maps
- AI allies spawn within their team's formation
- 4-team support (A/B/C/D) with corner-based zones

### Free-For-All Spawning ✅

- Each player placed at point **maximally distant** from all others
- Uses greedy algorithm: each successive player at furthest candidate
- **8 FFA points** per map, pre-designed for optimal spread
- Auto-detected when only 1 team has players (PvP default)

### Spawn Validation ✅

- All spawns on walkable tiles (never on obstacles)
- Never overlap with another player
- BFS fallback to nearest valid tile if collision detected
- Works on all 9 maps including dense Maze layouts

### Map Configuration ✅

All 9 maps updated with:
- **`spawn_zones`**: Rectangular corner areas per team (A/B/C/D)
- **`ffa_points`**: 8 coordinates per map for FFA matches

Zone sizes scale with map: 3×3 (12×12), 4×4 (15×15), 5×5 (20×20), 6×6 (25×25).

### Integration

- Smart spawns **resolve at match start** (not join time)
- Lobby shows temporary positions; final positions calculated when match begins
- Respects team swaps made during lobby phase
- `update_match_config()` now accepts all 9 maps (was 4)

### Test Coverage

**96 spawn-specific tests** covering:
- Zone placement, compactness, team separation
- FFA distance guarantees
- Obstacle avoidance, no duplicates, bounds checking
- Parametrized across all 9 real maps
- 4v4, FFA-8, single-player, and 4-team scenarios

---

## Feature 3: Performance Monitoring Tool

**Problem:** Need to measure performance across different map sizes and player counts.

**Solution:** Real-time performance overlay.

### Client Metrics

Display in corner overlay (toggle on/off):
- **FPS** (target: 60, warning: <55, critical: <30)
- **Network latency** (target: <50ms local, <150ms remote)
- **Current tick count**
- **Match duration**

Color-coded: green (good), yellow (warning), red (critical)

### Server Metrics

Log to console:
- **Tick resolution time** (target: <100ms for 8 players)
- **FOV calculation time** (target: <50ms for 8 units)
- **AI decision time** (target: <100ms for 8 AI)

Log warnings when thresholds exceeded.

### Testing Goals

Use tool to measure:
- Performance impact of 20x20 vs 25x25 maps
- FPS with 2, 4, 6, 8 players
- AI pathfinding performance
- Long matches (50+ turns) for memory leaks

---

## Timeline

**Week 1:** Create larger map variants ✅ Complete
**Week 2:** Implement spawn system ✅ Complete
**Week 3:** Build performance tool
**Week 4:** Testing and optimization

---

**Document Version:** 2.0  
**Created:** February 12, 2026  
**Last Updated:** February 12, 2026  
**Status:** In Progress — Features 1 & 2 complete, Feature 3 next
