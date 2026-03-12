# Phase 27 — PVPVE Dungeon Map

**Goal:** Create a new PVPVE game mode that uses WFC dungeon generation to produce a large procedural map where 2–4 player teams spawn in separate corners, fight PVE enemies and loot chests throughout the dungeon, and ultimately hunt down and eliminate rival teams. A boss encounter in the center provides high-risk/high-reward loot.

**Status:** Phase E complete — Phase F awaiting implementation

---

## Table of Contents

1. [Design Overview](#1-design-overview)
2. [Phase A — Data Model & Match Type](#phase-a--data-model--match-type)
3. [Phase B — WFC Generation for PVPVE Layout](#phase-b--wfc-generation-for-pvpve-layout)
4. [Phase C — Match Manager PVPVE Flow](#phase-c--match-manager-pvpve-flow)
5. [Phase D — Victory Conditions & PVE Team](#phase-d--victory-conditions--pve-team)
6. [Phase E — Lobby & UI Integration](#phase-e--lobby--ui-integration)
7. [Phase F — Balance & Tuning](#phase-f--balance--tuning)
8. [File Change Summary](#file-change-summary)
9. [Test Plan](#test-plan)
10. [Future Considerations](#future-considerations)

---

## 1. Design Overview

### Concept

A competitive dungeon crawl where multiple player teams spawn in opposite corners of a WFC-generated dungeon. Teams must:

1. **Explore** — navigate the procedural dungeon layout
2. **Fight PVE** — kill monsters that populate the rooms for XP/loot
3. **Loot** — open chests and collect gear drops to power up
4. **Eliminate** — find and wipe out rival player teams

The **last team standing** wins.

### Map Layout

```
 ┌──────────────────────────────────────────────────────┐
 │ [SPAWN A]  ──  [safe]  ──  [enemy]  ──  [SPAWN C]   │
 │     │           │            │              │        │
 │  [safe]     [enemy]      [loot]         [safe]      │
 │     │           │            │              │        │
 │  [enemy]    [loot]    ╔══════════╗      [enemy]     │
 │     │           │      ║  BOSS   ║         │        │
 │  [loot]     [enemy]   ║  ARENA  ║      [loot]      │
 │     │           │      ╚══════════╝         │        │
 │  [safe]     [loot]       [enemy]        [safe]      │
 │     │           │            │              │        │
 │ [SPAWN D]  ──  [enemy]  ──  [loot]  ──  [SPAWN B]   │
 └──────────────────────────────────────────────────────┘
```

**Key zones:**
- **Corner spawn rooms (4):** One per team. Proximity ramp guarantees safe/loot rooms nearby.
- **Outer ring:** Mix of enemy rooms and loot rooms. Lower difficulty enemies.
- **Inner ring:** Harder enemies, better loot. Guards the approach to center.
- **Center boss arena:** Boss + elite guards. Highest-value loot drops. High risk, high reward.

### Grid Size

**8×8 WFC grid = 64×64 tiles.** This is larger than any existing dungeon floor (max 6×6 = 48×48) but the PVPVE mode needs the extra space so 4 teams have room to explore before colliding.

### Teams & Spawning

| Team | Corner | Color |
|------|--------|-------|
| A | Top-left (0,0) | Blue |
| B | Bottom-right (7,7) | Red |
| C | Top-right (7,0) | Green |
| D | Bottom-left (0,7) | Yellow |
| PVE | Scattered | — (team "pve") |

2-team mode uses A + B (diagonal opposites for max distance). 3-team adds C. 4-team uses all four.

---

## Phase A — Data Model & Match Type

### A-1: New `MatchType` enum value

**File:** `server/app/models/match.py`

```python
class MatchType(str, Enum):
    PVP = "pvp"
    SOLO_PVE = "solo_pve"
    MIXED = "mixed"
    DUNGEON = "dungeon"
    PVPVE = "pvpve"        # NEW — competitive dungeon with PVE enemies
```

### A-2: New `MatchConfig` fields

**File:** `server/app/models/match.py`

Add optional PVPVE-specific config fields to `MatchConfig`:

```python
class MatchConfig(BaseModel):
    # ... existing fields ...

    # PVPVE settings
    pvpve_team_count: int = 2          # 2–4 player teams
    pvpve_pve_density: float = 0.5     # PVE enemy density multiplier (0.0–1.0)
    pvpve_boss_enabled: bool = True    # Spawn center boss
    pvpve_loot_density: float = 0.5    # Chest/loot density multiplier
    pvpve_grid_size: int = 8           # WFC grid size (default 8×8)
```

### A-3: New team for PVE enemies

PVE enemies spawn on a dedicated `"pve"` team string (not "a"/"b"/"c"/"d"). This piggybacks on the existing `player.team` field. The victory system filters out the PVE team so only player teams are checked.

**No new fields needed** — PVE enemies are `PlayerState` with `team="pve"`, `is_ai=True`, same as current dungeon enemies on `team="b"`.

### A-4: `MatchState` additions

**File:** `server/app/models/match.py`

Add a `team_pve` list to track PVE enemy IDs separately:

```python
class MatchState(BaseModel):
    # ... existing fields ...
    team_pve: list[str] = Field(default_factory=list)  # PVE enemy IDs (PVPVE mode)
```

### Tests (Phase A)

- Validate `MatchType.PVPVE` serializes/deserializes correctly
- Validate `pvpve_team_count` clamped to 2–4
- Validate `pvpve_pve_density` clamped to 0.0–1.0
- Config round-trip test with all new fields

---

## Phase B — WFC Generation for PVPVE Layout

The biggest piece: modify the WFC pipeline to produce a dungeon layout suited for PVPVE with 4 corner spawns and a center boss.

### B-1: New `FloorConfig` mode flag

**File:** `server/app/core/wfc/dungeon_generator.py`

Add a `pvpve_mode` flag and `pvpve_team_count` to `FloorConfig`:

```python
@dataclass
class FloorConfig:
    # ... existing fields ...
    pvpve_mode: bool = False       # Enable PVPVE layout (4 corner spawns, center boss)
    pvpve_team_count: int = 2      # Number of player teams (2–4)
```

Add a new factory method:

```python
@classmethod
def for_pvpve(cls, seed: int, team_count: int = 2,
              grid_size: int = 8, pve_density: float = 0.5,
              loot_density: float = 0.5, boss_enabled: bool = True) -> FloorConfig:
    """Create a FloorConfig optimized for PVPVE matches."""
    return cls(
        seed=seed,
        floor_number=1,              # PVPVE is single-floor
        grid_rows=grid_size,
        grid_cols=grid_size,
        enemy_density=pve_density,
        loot_density=loot_density,
        empty_room_chance=0.15,       # Fewer empties — more content to fight over
        max_enemies_per_room=4,
        enemy_roster=get_floor_roster(3),  # Mid-tier roster as baseline
        dungeon_style="balanced",
        batch_size=5,                 # More candidates for better layout
        map_name="PVPVE Dungeon",
        pvpve_mode=True,
        pvpve_team_count=team_count,
    )
```

### B-2: Room Decorator — PVPVE Layout Mode

**File:** `server/app/core/wfc/room_decorator.py`

This is the core layout change. When `pvpve_mode=True`, the decorator must:

#### B-2a: Force 4 corner spawn rooms

Instead of guaranteeing 1 spawn room, the PVPVE decorator **forces spawn rooms into the 4 corners** (or 2–3 corners for fewer teams).

**Corner mapping** (grid coordinates, 0-indexed):

| Team | Grid corner | Priority cells |
|------|-------------|----------------|
| A | (0, 0) | (0,0), (1,0), (0,1) |
| B | (max, max) | (max,max), (max-1,max), (max,max-1) |
| C | (max, 0) | (max,0), (max-1,0), (max,1) |
| D | (0, max) | (0,max), (1,max), (0,max-1) |

Algorithm:
1. For each active team (based on `pvpve_team_count`), scan the priority cells for the nearest flexible room.
2. Assign that room as a `spawn` room with a team tag (e.g., `spawn_a`, `spawn_b`, etc.).
3. If the exact corner cell is `structural` (solid wall), scan outward in a spiral from that corner until a flexible room is found.
4. Place `S` tiles at spawn slot positions in each assigned spawn room.

#### B-2b: Force boss room to center

Instead of placing the boss anywhere, force it to the **center of the grid**:

```
center_row = grid_rows // 2
center_col = grid_cols // 2
```

Scan a 2×2 block at `(center_row-1, center_col-1)` to `(center_row, center_col)` for the best flexible room. If no flexible room exists in the center block, expand the search radius outward.

The boss room gets:
- 1 boss enemy (`B` tile)
- 2–4 elite guard enemies (higher rarity budget — force `champion` on guards)
- Enhanced loot (`X` tiles for 2 chests in the boss room)

#### B-2c: Multi-spawn proximity ramp

Currently the proximity ramp creates a safety gradient around a single spawn room. For PVPVE, compute the proximity ramp **separately for each of the 4 spawn rooms**, then merge:

- Distance 1 from **any** spawn → `safe` (empty or loot only)
- Distance 2 from **any** spawn → `softened` (fewer enemies)
- Rooms equidistant from multiple spawns (contested zones) → normal or enemy-heavy

This means the areas immediately around each team's start are safe for gearing up, while the center and corridors between teams become contested battlegrounds.

#### B-2d: Difficulty gradient toward center

Add a **center-distance weighting** to enemy room decoration:

- Rooms closer to center → higher `maxEnemies` override, increased rarity budget
- Rooms at grid edges → lower enemy count, mostly normal rarity
- Boss room ring (distance 1 from center) → champion-tier guards

Implementation: after quota dealing, iterate enemy rooms and set a `difficulty_tier` based on Manhattan distance to center:

| Distance to center | Tier | Max enemies | Rarity budget |
|---------------------|------|-------------|---------------|
| 0 (center) | boss | Boss + 2–4 guards | super_unique / champion |
| 1 | elite | 4–5 | champion favored |
| 2 | hard | 3–4 | rare favored |
| 3+ | normal | 2–3 | normal / rare mix |

#### B-2e: Decorator config additions

New decorator config keys for PVPVE:

```python
_PVPVE_DECORATOR_DEFAULTS = {
    "guaranteeBoss": True,
    "guaranteeSpawn": True,        # Now means "guarantee N spawns" where N = team_count
    "guaranteeStairs": False,      # No stairs in PVPVE (single floor, no extraction)
    "enemyDensity": 0.50,
    "lootDensity": 0.50,
    "emptyRoomChance": 0.15,
    "maxEnemies": 4,
    "pvpve_mode": True,
    "pvpve_team_count": 4,
    "pvpve_boss_guards": 3,        # Number of elite guards in boss room
    "pvpve_boss_chests": 2,        # Number of chests in boss room
}
```

### B-3: Map Exporter — Multi-Team Spawn Zones

**File:** `server/app/core/wfc/map_exporter.py`

Currently the exporter collects all `S` tiles into a single `spawn_points` list and creates one `spawn_zones.a` bounding box. For PVPVE:

#### B-3a: Tagged spawn points

The decorator will tag spawn tiles with a team suffix (e.g., tile map stores `S` but the decorator metadata tracks which team each spawn room belongs to). The exporter reads these tags.

**Spawn point collection:**

```python
# Instead of one flat list, group by team
spawn_points_by_team = {"a": [], "b": [], "c": [], "d": []}
```

Each spawn tile's team assignment is determined by which spawn room it belongs to (passed via decorator metadata).

#### B-3b: Per-team spawn zones

Generate a `spawn_zones` dict with one zone per active team:

```python
spawn_zones = {}
for team_key, points in spawn_points_by_team.items():
    if points:
        xs = [p["x"] for p in points]
        ys = [p["y"] for p in points]
        # Expand slightly to give formation room
        spawn_zones[team_key] = {
            "x_min": max(0, min(xs) - 2),
            "y_min": max(0, min(ys) - 2),
            "x_max": min(width - 1, max(xs) + 2),
            "y_max": min(height - 1, max(ys) + 2),
        }
```

#### B-3c: PVE enemy team assignment

Currently all enemies are exported with no explicit team — `match_manager` puts them on `team_b`. For PVPVE, each room's `enemy_spawns` gets a `"team": "pve"` field so the match manager assigns them to the PVE team instead.

```python
# In room enemy_spawn dict
{
    "x": 15, "y": 22,
    "enemy_type": "demon",
    "team": "pve",  # NEW — tells match_manager which team
    "monster_rarity": "champion",
    ...
}
```

#### B-3d: Boss room metadata

Export a top-level `boss_room` field in the map JSON:

```python
"boss_room": {
    "id": "room_4_4",
    "bounds": {"x_min": 28, "y_min": 28, "x_max": 35, "y_max": 35},
    "enemy_spawns": [...],  # Boss + guards
    "chests": [{"x": 30, "y": 30}, {"x": 33, "y": 33}]
}
```

#### B-3e: Map type tag

The exported map gets `"map_type": "pvpve"` so the match manager can detect it:

```python
{
    "name": "PVPVE Dungeon",
    "width": 64,
    "height": 64,
    "map_type": "pvpve",
    "pvpve_team_count": 4,
    ...
}
```

### Tests (Phase B)

- **WFC layout tests:**
  - PVPVE FloorConfig generates 64×64 tile grid
  - Corner spawn rooms are placed within 1 cell of their target corners
  - Boss room is placed within 1 cell of grid center
  - All 4 spawn rooms are connected to the boss room (flood fill)
  - No spawn room is adjacent to another spawn room
- **Decorator tests:**
  - Proximity ramp operates around all spawn rooms independently
  - Rooms adjacent to spawns are safe/loot only
  - Difficulty gradient increases toward center
  - Boss room has boss + 2–4 guards + chests
- **Exporter tests:**
  - `spawn_zones` has entries for each active team (a/b/c/d)
  - `spawn_points` grouped correctly per team
  - Enemy spawns have `"team": "pve"` field
  - `boss_room` metadata is present
  - `map_type` is `"pvpve"`

---

## Phase C — Match Manager PVPVE Flow

### C-1: PVPVE match initialization

**File:** `server/app/core/match_manager.py`

Add PVPVE branch to `start_match()`:

```python
if match.config.match_type == MatchType.PVPVE:
    # 1. Generate procedural PVPVE dungeon
    pvpve_config = FloorConfig.for_pvpve(
        seed=match.state.dungeon_seed or random_seed(),
        team_count=match.config.pvpve_team_count,
        grid_size=match.config.pvpve_grid_size,
        pve_density=match.config.pvpve_pve_density,
        boss_enabled=match.config.pvpve_boss_enabled,
        loot_density=match.config.pvpve_loot_density,
    )
    result = generate_dungeon_floor(config=pvpve_config)
    map_id = f"pvpve_{match.match_id}"
    register_runtime_map(map_id, result.game_map)
    match.config.map_id = map_id

    # 2. Team assignment — distribute players across teams
    _assign_pvpve_teams(match)

    # 3. Spawn players in their team zones (uses spawn_zones from map)
    _resolve_pvpve_spawns(match)

    # 4. Init dungeon state (doors, chests, ground items)
    _init_dungeon_state(match)

    # 5. Spawn PVE enemies on "pve" team
    _spawn_pvpve_enemies(match)

    # 6. Compute initial FOV (per-team fog of war)
    _compute_initial_fov(match)
```

### C-2: Team assignment logic

**New function:** `_assign_pvpve_teams(match)`

Distributes human players + their AI allies across the configured number of teams:

```
2 teams: A vs B (diagonal corners — max separation)
3 teams: A vs B vs C
4 teams: A vs B vs C vs D
```

Assignment rules:
- Host goes to team A
- Other humans distributed round-robin across teams
- AI allies fill remaining slots per team
- Each team gets up to `max_players // team_count` slots
- Populate `match.state.team_a`, `team_b`, `team_c`, `team_d` accordingly

### C-3: PVE enemy spawning

**New function:** `_spawn_pvpve_enemies(match)`

Similar to existing `_spawn_dungeon_enemies()` but:
- Reads `enemy_spawns` from all rooms in the map
- Sets `team="pve"` on each enemy (from the spawn data's team field)
- Tracks enemy IDs in `match.state.team_pve`
- Applies monster rarity (champion, rare, super_unique) from the spawn data
- Boss room enemies get enhanced stats via rarity
- Does NOT count PVE enemies toward any player team

### C-4: Fog of War per team

The existing FOV system computes visibility per unit. In PVPVE, each player team should share FOV with teammates (already works — FOV is per-unit, and the client shows what your team sees). **No changes needed** to the FOV system — it already works per-unit and the client already filters.

However, enemy positions from other player teams should only be visible within FOV. The existing state broadcast already filters by visibility — confirm this works with 4 teams.

### C-5: No floor advancement

PVPVE is a **single-floor** mode. No stairs, no floor advancement. The stairs system is disabled (decorator sets `guaranteeStairs: false`). The match ends when only one player team survives.

### Tests (Phase C)

- PVPVE match starts with procedural map generation
- Players are distributed across correct number of teams
- PVE enemies spawn on `"pve"` team
- `match.state.team_pve` is populated
- Each player team spawns in their designated corner zone
- PVE enemies do not appear in `team_a`, `team_b`, `team_c`, or `team_d` lists
- FOV works correctly with 4+ teams

---

## Phase D — Victory Conditions & PVE Team

### D-1: Victory check update

**File:** `server/app/core/combat.py`

Modify `check_team_victory()` to accept an optional `excluded_teams` parameter:

```python
def check_team_victory(
    players: list[PlayerState],
    team_a: list[str],
    team_b: list[str],
    team_c: list[str] | None = None,
    team_d: list[str] | None = None,
    excluded_teams: set[str] | None = None,  # NEW — teams to ignore for victory
) -> str | None:
```

When `excluded_teams` is provided (e.g., `{"pve"}`), units on those teams are not considered when counting surviving teams. This means:

- PVE enemies dying doesn't trigger victory
- Victory triggers when only 1 player team has living members
- If all player teams die (e.g., PVE wipe), result is `"draw"`

### D-2: Death phase integration

**File:** `server/app/core/turn_phases/deaths_phase.py`

Pass `excluded_teams={"pve"}` when calling `check_team_victory()` in PVPVE matches. The match type needs to be accessible in the death phase context.

**Approach:** Add `match_type` to the turn context dict that flows through `resolve_turn()`. When `match_type == "pvpve"`, pass the exclusion set.

### D-3: PVE enemy AI behavior

PVE enemies should be hostile to **all player teams** equally. Currently dungeon enemies target `team_a` by default. For PVPVE:

**File:** `server/app/core/ai_behavior.py`

When a PVE enemy (`team="pve"`) picks targets, it should consider **all non-PVE units** as valid enemies:

```python
def _get_valid_targets(unit, all_players):
    if unit.team == "pve":
        # PVE: target any living non-PVE unit
        return [p for p in all_players.values()
                if p.is_alive and p.team != "pve"]
    else:
        # Normal: target units on other teams
        return [p for p in all_players.values()
                if p.is_alive and p.team != unit.team]
```

This should mostly already work since the AI targets enemies (non-allies). Verify and adjust the `are_allies()` function:

**File:** `server/app/core/combat.py`

The existing `are_allies()` checks `unit_a.team == unit_b.team`. This naturally means PVE enemies (team "pve") are hostile to all player teams and vice versa. **No change needed** — just verify in tests.

### D-4: Player teams hostile to each other

Players on team A should be hostile to teams B, C, D, and PVE. The `are_allies()` check already handles this since teams have different strings. Verify:
- Team A players can attack Team B players (and vice versa)
- Team A players can attack PVE enemies
- PVE enemies can attack any player team
- Friendly fire within the same team is prevented

### Tests (Phase D)

- Victory only triggers when 1 player team survives (PVE dying doesn't end match)
- All player teams eliminated → draw
- PVE enemies target all player teams
- Player teams are hostile to each other
- `are_allies()` correctly identifies same-team as allies, different-team as enemies
- PVE team excluded from victory calculation
- Match continues as long as 2+ player teams alive (even if PVE is eliminated)

---

## Phase E — Lobby & UI Integration ✅

> **Implemented 2026-03-09** — All E sub-phases complete plus bonus multi-AI-team feature.

### E-1: Match creation — PVPVE option ✅

**File:** `client/src/components/Lobby/Lobby.jsx`

- Added `pvpve` to the non-joinable match filter (same as dungeon — must join from TownHub)
- PVPVE matches appear in the lobby list with the `tag-pvpve` badge

### E-2: Waiting room — team display ✅

**File:** `client/src/components/WaitingRoom/WaitingRoom.jsx`

- Added `{ id: 'pvpve', label: 'PVPVE' }` to MATCH_TYPES array
- Added full PVPVE config panel (shown when matchType === 'pvpve'):
  - **Team Count** slider: 2–4 (default 2)
  - **PVE Density** dropdown: Low (0.3) / Medium (0.5) / High (0.7)
  - **Grid Size** dropdown: 6×6 / 8×8 / 10×10
  - **Boss Enabled** toggle (default on)
  - **AI Hero Teams** slider: 0 to (teamCount - 1) — allows up to 3 AI-controlled hero teams
  - **AI Team Sizes** per AI team: 1–5 units each
- Existing AI opponents/allies sliders remain for all non-PVP modes (including PVPVE)
- Procedural banner shows: "Competitive dungeon — teams spawn in corners, fight PVE, and hunt each other"
- Theme selector also available for PVPVE mode
- AI units labeled 'PVE' when team === 'pve'

### E-3: In-match HUD ✅

**Files:** `client/src/components/HeaderBar/HeaderBar.jsx`, `client/src/context/reducers/combatReducer.js`

- Added `PVPVE_TEAM_COLORS` constant (a=#4a8fd0, b=#e04040, c=#40c040, d=#d4a017)
- Header shows `.header-mode-badge--pvpve` class
- Header shows `.header-team-indicator` with team name in team color
- Header shows `.header-teams-remaining` counter ("Teams: X/Y")
- `combatReducer` now sets `isPvpve` flag on MATCH_START
- `combatReducer` now extracts `bossRoom` from payload on MATCH_START
- `combatReducer` now stores `teamEliminations` from TURN_RESULT payload

### E-4: Match type tag styling ✅

**Files:** `client/src/styles/components/_lobby.css`, `_header-bar.css`, `_waiting-room.css`, `_post-match.css`

- `.tag-pvpve` — purple gradient badge in lobby match list
- `.tag-dungeon` — teal gradient badge (added alongside)
- `.header-mode-badge--pvpve` — purple badge in header bar
- `.header-team-indicator` — colored team label
- `.header-teams-remaining` — teams-alive counter
- `.pvpve-team-size-slider` — per-AI-team size slider in waiting room
- `outcome-pvpve_victory` / `outcome-pvpve_defeat` — post-match outcome banners with pulse animation

### E-5: Minimap updates ✅

**Files:** `client/src/canvas/minimapRenderer.js`, `client/src/components/MinimapPanel/MinimapPanel.jsx`, `client/src/components/Arena/Arena.jsx`

- Added `BLIP_TEAM` color map (a=blue, b=red, c=green, d=yellow, pve=gray)
- `drawMinimap()` now accepts `isPvpve` and `bossRoom` parameters
- Boss room marker: pulsing red rectangle + circle indicator in expanded mode
- Enemy player teams rendered in their team color; PVE enemies use rarity-based colors with gray base
- Existing rarity enlargement logic preserved for PVE enemies
- Arena passes `isPvpve` and `bossRoom` props through MinimapPanel

### E-6: Post-match screen ✅

**File:** `client/src/components/PostMatch/PostMatchScreen.jsx`

- Added `pvpve_victory` and `pvpve_defeat` outcome types with thematic messages
- `isPvpve` flag computed from `summary?.matchType === 'pvpve'`
- Scoreboard shown for PVPVE (previously hidden for all dungeon-type modes)
- PVE team (`team === 'pve'`) filtered from scoreboard teamGroups
- Team comparison bars limited to exactly 2 non-pve teams (skipped for 3–4 team matches)
- `pve: 'PVE'` added to teamLabels
- Meta section shows PVE kills and boss kill for PVPVE
- Winner check extended for teams c/d in Arena.jsx

### E-extra: Multi AI team server config ✅

**Files:** `server/app/models/match.py`, `server/app/core/match_manager.py`

- Added `pvpve_ai_team_count: int = 0` and `pvpve_ai_team_sizes: list[int]` to MatchConfig model
- `update_match_config()` now handles all PVPVE fields with validation:
  - `pvpve_team_count` clamped to 2–4
  - `pvpve_pve_density` clamped to 0.0–1.0
  - `pvpve_grid_size` restricted to {6, 8, 10}
  - `pvpve_ai_team_count` clamped to 0–(team_count - 1)
  - `pvpve_ai_team_sizes` items clamped to 1–5
- Both `update_match_config()` return dict and `get_match_config_payload()` include all PVPVE fields

### Tests (Phase E)

- Lobby can create PVPVE match with all config options
- Match type tag renders with correct styling
- Waiting room shows team assignments
- HUD shows team indicators and elimination notifications

---

## Phase F — Balance & Tuning

### F-1: PVE scaling based on team count

More teams = more total players = PVE should be tougher to compensate:

| Teams | PVE HP multiplier | PVE damage multiplier | Enemy density adjustment |
|-------|-------------------|-----------------------|--------------------------|
| 2 | 1.0× | 1.0× | Base density |
| 3 | 1.15× | 1.1× | +10% more enemy rooms |
| 4 | 1.3× | 1.2× | +20% more enemy rooms |

### F-2: Loot distribution

- **Chests:** First to open gets the loot (already works this way)
- **Enemy drops:** Loot drops on the ground at the enemy's death position (existing behavior). Any team can pick it up.
- **Boss drops:** Boss drops 3–5 high-quality items on the ground. Creates a contested loot pile that teams may fight over.
- **Chest placement:** Ensure roughly equal loot opportunities near each spawn (decorator proximity ramp handles this — each corner gets nearby loot rooms).

### F-3: Respawn policy

For PVPVE, **no respawns**. When a player dies, they're dead (permadeath, consistent with dungeon mode). When all members of a team are dead, that team is eliminated.

### F-4: Dungeon theme

PVPVE maps use the existing theme system. Default to random theme selection, or allow host to pick in lobby. The grimdark themes (e.g., `bleeding_catacombs`, `bone_cathedral`) fit the competitive feel.

### F-5: Boss encounter design

The center boss should be a meaningful challenge:

- **Boss type:** Pulled from super_uniques pool or boss roster (floor tier 3–4 equivalent)
- **Boss guards:** 2–4 champion-tier enemies
- **Boss HP:** 2× normal boss HP (multiple teams may converge, so it should survive some punishment)
- **Boss behavior:** Standard AI — attacks nearest enemy. Will attack whichever team(s) are in the room.
- **Boss drops:** 100% drop rate, 3–5 items, guaranteed rare+ quality, 2× gold. The high-value loot pile incentivizes teams to race for the boss kill.
- **Boss room chests:** 2 chests in the boss room provide additional loot incentive.

### F-6: Map size tuning guide

| Grid size | Tile dimensions | Best for | Match length (est.) |
|-----------|-----------------|----------|---------------------|
| 6×6 | 48×48 | 2 teams, fast | Short |
| 8×8 | 64×64 | 2–4 teams, standard | Medium |
| 10×10 | 80×80 | 4 teams, epic | Long |

---

## File Change Summary

### Server files

| File | Change | Phase |
|------|--------|-------|
| `server/app/models/match.py` | Add `MatchType.PVPVE`, PVPVE config fields, `team_pve` | A |
| `server/app/core/wfc/dungeon_generator.py` | Add `pvpve_mode` to `FloorConfig`, `for_pvpve()` factory | B |
| `server/app/core/wfc/room_decorator.py` | PVPVE layout mode: 4 corner spawns, center boss, multi-spawn proximity ramp, difficulty gradient | B |
| `server/app/core/wfc/map_exporter.py` | Multi-team spawn zones, `boss_room` metadata, PVE team tags, `map_type: pvpve` | B |
| `server/app/core/match_manager.py` | `_assign_pvpve_teams()`, `_spawn_pvpve_enemies()`, `_resolve_pvpve_spawns()`, PVPVE match init flow | C |
| `server/app/core/combat.py` | `excluded_teams` parameter in `check_team_victory()` | D |
| `server/app/core/turn_phases/deaths_phase.py` | Pass `excluded_teams` for PVPVE matches | D |
| `server/app/core/ai_behavior.py` | Verify PVE targets all player teams (may need minor adjustment) | D |
| `server/app/core/spawn.py` | No changes needed — already supports 4 team zones | — |

### Client files

| File | Change | Phase |
|------|--------|-------|
| `client/src/components/Lobby/Lobby.jsx` | PVPVE match type option + config UI | E |
| `client/src/components/WaitingRoom/` | Team assignment display | E |
| `client/src/components/HeaderBar/` | Team indicators, elimination banners | E |
| `client/src/components/HUD/` | Teams remaining counter | E |
| `client/src/canvas/minimapRenderer.js` | Team-colored dots, boss room marker | E |
| `client/src/components/PostMatch/` | Multi-team stats display | E |
| `client/src/styles/components/_lobby.css` | `.tag-pvpve` styling | E |
| `client/src/context/reducers/combatReducer.js` | Handle PVPVE state (team eliminations, etc.) | E |

### Config files

| File | Change | Phase |
|------|--------|-------|
| `server/configs/enemies_config.json` | No changes — existing enemies used | — |
| `server/configs/loot_tables.json` | Possibly add PVPVE boss loot table | F |
| `server/configs/monster_rarity_config.json` | No changes — existing rarity system used | — |

---

## Test Plan

### Unit tests (new file: `server/tests/test_pvpve.py`)

| # | Test | Phase |
|---|------|-------|
| 1 | `MatchType.PVPVE` enum serialization | A |
| 2 | `MatchConfig` PVPVE fields default values | A |
| 3 | `MatchConfig` PVPVE fields validation (clamping) | A |
| 4 | `FloorConfig.for_pvpve()` produces correct grid size | B |
| 5 | PVPVE decorator places 4 spawn rooms in corners | B |
| 6 | PVPVE decorator places 2 spawn rooms for 2-team mode | B |
| 7 | PVPVE decorator places boss room near center | B |
| 8 | All corner spawns connected to center (flood fill) | B |
| 9 | Proximity ramp around all spawn rooms | B |
| 10 | Difficulty gradient: center rooms harder than edge | B |
| 11 | Boss room has boss + guards + chests | B |
| 12 | Map exporter produces per-team spawn zones | B |
| 13 | Map exporter tags enemies with `team: "pve"` | B |
| 14 | Map exporter includes `boss_room` metadata | B |
| 15 | Map exporter sets `map_type: "pvpve"` | B |
| 16 | `_assign_pvpve_teams()` distributes players correctly (2 teams) | C |
| 17 | `_assign_pvpve_teams()` distributes players correctly (4 teams) | C |
| 18 | PVE enemies spawn on `"pve"` team | C |
| 19 | Player teams spawn in correct corner zones | C |
| 20 | `check_team_victory()` with `excluded_teams={"pve"}` ignores PVE | D |
| 21 | Victory when 1 player team survives + PVE alive → winner declared | D |
| 22 | All player teams dead → draw (even if PVE alive) | D |
| 23 | PVE enemies target all player teams | D |
| 24 | Player teams hostile to each other | D |
| 25 | Same-team units are allies (`are_allies()`) | D |
| 26 | No respawns — dead players stay dead | D |

### Integration tests

| # | Test | Phase |
|---|------|-------|
| 27 | Full PVPVE match: create → start → generate map → spawn → verify layout | C |
| 28 | PVPVE match runs 10 turns without errors | C |
| 29 | Team elimination triggers correct notification | D |
| 30 | Last team standing wins match | D |
| 31 | 4-team PVPVE match with all teams populated | C |
| 32 | Boss kill drops loot on ground | F |

**Target: ~32 new tests**

---

## Implementation Order

```
Phase A  →  Phase B  →  Phase C  →  Phase D  →  Phase E  →  Phase F
(model)    (WFC gen)   (manager)   (victory)    (UI)       (balance)
```

Each phase is independently testable. Phase B is the largest and can be further split:

```
B-1 (FloorConfig) → B-2 (Decorator) → B-3 (Exporter)
```

### Recommended implementation sequence

1. **Phase A** — Data model additions (small, foundation for everything)
2. **Phase B-1** — FloorConfig PVPVE factory
3. **Phase B-2a/b** — Decorator corner spawns + center boss
4. **Phase B-2c/d** — Proximity ramp + difficulty gradient
5. **Phase B-3** — Exporter multi-team output
6. **Phase C** — Match manager PVPVE flow
7. **Phase D** — Victory conditions + PVE AI targeting
8. **Phase E** — Lobby + UI
9. **Phase F** — Balance tuning (iterative)

---

## Future Considerations

- **Shrinking fog / storm circle:** Force teams toward center over time (battle royale mechanic)
- **Respawn timers:** Optional mode where dead players respawn after N turns (longer matches)
- **Objective-based variants:** King of the Hill (hold boss room), Capture the Flag (grab relic from opponents' base)
- **Spectator mode:** Eliminated teams can watch remaining teams
- **PVE scaling by proximity:** PVE enemies near the center could scale with how many teams are nearby
- **Team-colored territory:** Minimap shows which areas each team has explored (fog of war reveal zones)
- **Environmental hazards:** Trap rooms that deal damage — adds dungeon crawl danger
- **Resource contention:** Limited powerful items (only 1 legendary drops per map) drives conflict
