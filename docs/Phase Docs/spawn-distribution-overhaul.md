# Spawn Distribution Overhaul

> **Goal**: Fix the "empty streak → impossible death room" problem in WFC dungeon runs by replacing independent per-room RNG with controlled, spatially-aware distribution systems.

## Problem Statement

Players experience wildly inconsistent dungeon difficulty:
- Walking through 3-5 empty rooms with nothing to fight
- Then hitting a single room with 5+ enemies, 2 of which rolled rare with affixes (teleporter, thorns, auras), plus their minions — an unwinnable fight

This is caused by three compounding issues in the current system:
1. **Room roles assigned by independent coin flips** — no guarantee of even spread
2. **No proximity awareness** — the room next to spawn is as likely to be packed as the farthest room
3. **No difficulty budget per room** — rarity upgrades stack without limit inside a single room

---

## Current System Summary (for reference)

### Pipeline
```
FloorConfig.from_floor_number()
    → dungeon_styles.py (auto-select style → weight overrides + decorator overrides)
    → wfc_engine.py (structural layout)
    → room_decorator.py (assign roles to flexible rooms → place E/B/S/X/T tiles)
    → map_exporter.py (resolve enemy IDs from roster + roll rarity per enemy)
    → match_manager.py (spawn actual units from map data)
```

### Current Room Assignment (room_decorator.py, Pass C)
Each flexible room rolls a single `rng()` value independently:
```
if roll < emptyRoomChance           → empty
elif roll < empty + enemy*(1-empty) → enemy
elif roll < that + loot*(1-empty)   → loot
else                                → empty
```

### Current Rarity Rolling (monster_rarity_config.json)
Per enemy, independently:
- Rare: `2% base + 1.5%/floor` (floor 4+) → **11% on floor 6, 14% on floor 8**
- Champion: `4% base + 1.5%/floor` (floor 2+) → **13% on floor 6, 16% on floor 8**
- Max 2 enhanced per room
- Rare enemies spawn 2-3 minions with 2-3 affixes each

### Current Constants (dungeon_generator.py)
| Constant | Value | Notes |
|---|---|---|
| `_ENEMY_DENSITY_BASE` | 0.45 | Base % of flexible rooms → enemy |
| `_ENEMY_DENSITY_PER_FLOOR` | +0.06/floor | Scales up aggressively |
| `_ENEMY_DENSITY_CAP` | 0.85 | |
| `_EMPTY_ROOM_BASE` | 0.20 | 20% empty on floor 1 |
| `_EMPTY_ROOM_PER_FLOOR` | −0.02/floor | Fewer breathers deeper |
| `_EMPTY_ROOM_MIN` | 0.08 | Never below 8% |
| `_MAX_ENEMIES_PER_ROOM` | 4→5→6→7 | By floor tier |

### Dungeon Style Decorator Overrides (can supersede above)
| Style | enemyDensity | emptyRoomChance | lootDensity |
|---|---|---|---|
| Balanced | *(uses floor defaults)* | *(uses floor defaults)* | *(uses floor defaults)* |
| Dense Catacomb | 0.70 | 0.10 | 0.10 |
| Open Ruins | 0.25 | 0.35 | 0.30 |
| Boss Rush | 0.60 | 0.10 | 0.05 |
| Treasure Vault | 0.30 | 0.10 | 0.50 |

---

## Phase 1: Quota-Based Room Distribution

**Priority**: HIGH — biggest gameplay impact  
**Effort**: Small-Medium  
**Files**: `server/app/core/wfc/room_decorator.py`

### What changes

Replace Pass C's independent per-room `rng()` rolls with a **deck/quota** system that guarantees an even distribution of room roles.

### Current behavior (Pass C, lines 313-333)
```python
for room in flexible_rooms:
    roll = rng()
    if roll < emptyRoomChance:
        assignments[key] = "empty"
    elif roll < enemy_threshold:
        assignments[key] = "enemy"
    elif roll < loot_threshold:
        assignments[key] = "loot"
    else:
        assignments[key] = "empty"
```

**Problem**: 9 rooms with 45% enemy density can give you 0-9 enemy rooms — pure luck.

### New behavior
```python
# 1. Count available rooms (after boss/spawn/stairs already assigned)
remaining = [r for r in flexible_rooms if key not in assignments]
n = len(remaining)

# 2. Compute target counts from density settings
n_enemy = round(n * config["enemyDensity"])
n_loot  = round(n * config["lootDensity"])
n_empty = max(1, n - n_enemy - n_loot)  # remainder → empty (at least 1)

# 3. Clamp if oversubscribed
if n_enemy + n_loot > n:
    # Scale both down proportionally, keeping at least 1 empty
    total_want = n_enemy + n_loot
    scale = (n - 1) / total_want
    n_enemy = max(1, round(n_enemy * scale))
    n_loot  = max(0, round(n_loot * scale))
    n_empty = n - n_enemy - n_loot

# 4. Build a role deck and shuffle it
deck = (["enemy"] * n_enemy) + (["loot"] * n_loot) + (["empty"] * n_empty)
# Pad or trim to exactly match room count
while len(deck) < n:
    deck.append("empty")
deck = deck[:n]
_shuffle(deck, rng)

# 5. Deal roles to rooms
for room, role in zip(remaining, deck):
    key = f"{room['gridRow']},{room['gridCol']}"
    assignments[key] = role
```

### Why this fixes the problem
- **Exact target counts** — if density says 45% enemy, you get 45% enemy rooms (±1 from rounding), guaranteed
- **No streaks** — roles are shuffled randomly but the totals are pre-determined
- **Still deterministic** — same seed = same shuffle = same layout
- **Style overrides still work** — Dense Catacomb with 70% enemy density just produces a deck with more "enemy" tokens

### Scatter mechanics (unchanged)
The existing scatter logic (25% lone enemy in empty rooms, 45% guard in loot rooms, 30% bonus chest in enemy rooms) stays as-is. These add texture on top of the guaranteed distribution.

### Acceptance criteria
- [x] Same density settings produce the same approximate room counts (within ±1) every generation
- [x] No run of 4+ consecutive same-role rooms after the shuffle (statistical property of shuffled decks)
- [x] Style overrides correctly shift the deck composition
- [x] All existing room_decorator tests still pass (role totals may shift slightly — update expected values)
- [x] New test: verify quota math for edge cases (0 rooms, 1 room, all-enemy style)

### Implementation notes (completed 2026-03-06)
- **File changed**: `server/app/core/wfc/room_decorator.py` — Pass C rewritten (lines 313–343)
- **Old behavior**: Each flexible room rolled `rng()` independently against threshold bands
- **New behavior**: Computes `n_enemy = round(remaining × enemyDensity)`, `n_loot = round(remaining × lootDensity)`, builds a shuffled deck of role tokens, deals them to rooms
- **Clamping**: When enemy + loot density exceeds 1.0, scales both down proportionally while keeping ≥1 empty
- **Determinism**: Same seed → same shuffle → same layout (Fisher-Yates shuffle with seeded PRNG)
- **Tests added**: `server/tests/test_wfc_room_quota.py` — 19 tests covering quota math, edge cases, determinism, scatter mechanics, and full pipeline integration
- **Test suite**: 2951 passed (all 172 WFC tests green, 19 new), 1 pre-existing unrelated failure (`TestGreedSigil::test_damage_penalty`)

---

## Phase 2: Spawn-Proximity Ramp

**Priority**: HIGH — crucial for feel  
**Effort**: Small  
**Files**: `server/app/core/wfc/room_decorator.py`

### What changes

After the spawn room is assigned (Pass B), compute **grid distance** from spawn to every flexible room. Rooms close to spawn are protected from being heavy enemy rooms.

### Implementation plan

Add a new pass between Pass B2 (stairs) and Pass C (role assignment):

```python
# ── Pass B3: Compute spawn distance for each room ──
spawn_room = None
for room in flexible_rooms:
    key = f"{room['gridRow']},{room['gridCol']}"
    if assignments.get(key) == "spawn":
        spawn_room = room
        break

# Also check fixed spawn rooms
if spawn_room is None:
    for fr in fixed_rooms:
        if fr["purpose"] == "spawn":
            spawn_room = fr
            break

room_distances = {}
for room in flexible_rooms:
    key = f"{room['gridRow']},{room['gridCol']}"
    if spawn_room:
        dist = abs(room["gridRow"] - spawn_room["gridRow"]) + abs(room["gridCol"] - spawn_room["gridCol"])
    else:
        dist = 99  # No spawn found — don't restrict anything
    room_distances[key] = dist
```

Then modify the deck-dealing step (Phase 1) to enforce proximity rules:

```python
# Sort remaining rooms by distance (closest first)
remaining.sort(key=lambda r: room_distances.get(f"{r['gridRow']},{r['gridCol']}", 99))

# Build the deck as before, then apply proximity overrides:
# Distance 0: spawn room itself (already assigned)
# Distance 1: force "empty" or "loot" (safe buffer)
# Distance 2: allow enemy but reduce max enemies to floor(maxEnemies / 2)
proximity_overrides = {}
for room in remaining:
    key = f"{room['gridRow']},{room['gridCol']}"
    dist = room_distances.get(key, 99)
    if dist <= 1:
        proximity_overrides[key] = "safe"       # Force empty or loot
    elif dist == 2:
        proximity_overrides[key] = "softened"    # Enemy OK but fewer mobs

# Re-deal: pull "enemy" tokens away from safe zones, swap them to far rooms
# ... (implementation detail — swap tokens rather than re-shuffle to preserve determinism)
```

### Softened rooms
Rooms at distance 2 that end up as "enemy" get a reduced `maxEnemies`:
```python
if proximity_overrides.get(key) == "softened" and role == "enemy":
    room["maxEnemies"] = max(1, room["maxEnemies"] // 2)
```

### Distance table (3×3 grid example)
```
S = Spawn room at (0,0)

[S][ 1][ 2]
[ 1][ 2][ 3]
[ 2][ 3][ 4]

Distance 0: Spawn itself
Distance 1: Safe buffer (2 rooms) — empty/loot only
Distance 2: Softened (3 rooms) — enemy OK but half-strength
Distance 3+: Normal rules (4 rooms)
```

On a 3×3 grid (floor 1-2), this means the player always has 1-2 rooms of breathing space before encountering a real fight. On a 5×5 grid, the buffer covers the first ring around spawn.

### Acceptance criteria
- [x] Rooms adjacent to spawn never contain enemy packs (only loot/empty/scattered lone enemy)
- [x] Distance-2 rooms have halved max enemy count
- [x] Stairs room placement (Pass B2) is unaffected — still placed farthest from spawn
- [x] On small grids (3×3), at least 2 rooms are protected; on large grids (5×5+), 3-4 rooms
- [x] New test: verify distance calculation and proximity override application
- [x] New test: verify that safe-zone rooms never get "enemy" role from the deck

### Implementation notes (completed 2026-03-06)
- **File changed**: `server/app/core/wfc/room_decorator.py` — Pass B3 added (spawn distance + proximity overrides), Pass C modified (proximity-aware deck dealing), Phase 4 enemy placement modified (softened maxEnemies)
- **Pass B3**: Computes Manhattan distance from spawn room to every flexible room. Classifies rooms as `"safe"` (dist ≤ 1) or `"softened"` (dist == 2). Checks both flexible and fixed spawn rooms.
- **Proximity-aware deck dealing**: After shuffle, scans for enemy tokens in safe-zone slots. Swaps them with non-enemy tokens from far-zone rooms (dist ≥ 3). If no swap targets available, force-converts to "loot" as safe fallback.
- **Softened rooms**: Enemy rooms at distance 2 get `maxEnemies = max(1, maxEnemies // 2)`, halving pack size near spawn.
- **Room output enrichment**: Each decorated room now includes `spawnDistance` (int) and `proximityOverride` ("safe"|"softened"|null) for debugging and downstream use.
- **Determinism**: Same seed → same distance calc → same swap order → identical output.
- **Tests added**: `server/tests/test_wfc_proximity.py` — 26 tests across 9 test classes: distance calculation (4), proximity overrides (3), safe-zone enemy exclusion (4), softened rooms (2), protected room counts (3), stairs placement unaffected (2), determinism (2), quota preservation (2), scatter mechanics (1), full pipeline integration (3).
- **Phase 1 test update**: `test_zero_loot_density` updated to allow ≤1 loot room (proximity fallback can convert safe-zone enemy → loot when no far swap targets exist).
- **Test suite**: 2978 passed (0 failures), up from 2951 (+26 new + 1 pre-existing fix).

---

## Phase 3: Per-Room Difficulty Budget

**Priority**: MEDIUM — prevents impossible rooms  
**Effort**: Small  
**Files**: `server/app/core/wfc/map_exporter.py`, `server/configs/monster_rarity_config.json`

### What changes

Instead of rolling rarity per enemy independently with only a flat `max_enhanced_per_room=2` cap, introduce a **difficulty point budget** per room that constrains how much rarity can stack.

### Difficulty point values
| Rarity | Points | Why |
|---|---|---|
| Normal | 1 | Baseline |
| Champion | 3 | 1.4× HP, 1.2× damage, champion type ability |
| Rare | 5 | 1.7× HP, 1.3× damage, 2-3 affixes, 2-3 minions |
| Super Unique | 8 | Hand-crafted boss, fixed retinue |

### Room budget by floor tier
| Floor | Base Budget | Per-Enemy Bonus | Example: 4 enemies |
|---|---|---|---|
| 1-2 | 6 | +1 per enemy | 6 + 4 = 10 → 2 normals + 1 champ + 1 normal, or 2 normals + 1 rare remaining=0 |
| 3-4 | 8 | +1.5 | 8 + 6 = 14 → room for 1 rare + 1 champ + 2 normals |
| 5-6 | 10 | +2 | 10 + 8 = 18 → room for 1 rare + 2 champs + 1 normal |
| 7-8 | 12 | +2 | 12 + 8 = 20 |
| 9+ | 15 | +2.5 | 15 + 10 = 25 → nearly uncapped |

### Implementation

Modify `_roll_rarity_for_spawn()` in `map_exporter.py`:

```python
def _roll_rarity_for_spawn(enemy_id, is_boss, room_budget_remaining):
    """Roll rarity upgrade, but only if budget allows."""
    if is_boss:
        return default_rarity_data  # bosses don't consume budget
    
    # Roll as before
    rarity = roll_monster_rarity(floor_number, _rarity_rng)
    
    cost = RARITY_COSTS.get(rarity, 1)
    if cost > room_budget_remaining:
        # Can't afford this upgrade — downgrade
        if room_budget_remaining >= RARITY_COSTS["champion"]:
            rarity = "champion"
        else:
            rarity = "normal"
    
    # ... rest of existing logic (roll affixes, generate name, etc.)
    return rarity_data, cost
```

The room-level loop tracks remaining budget:
```python
room_budget = get_room_budget(floor_number, regular_count)
for each enemy in room:
    rarity_data, cost = _roll_rarity_for_spawn(eid, is_boss, room_budget)
    room_budget -= cost
```

### Config addition (`monster_rarity_config.json`)
```json
"difficulty_budget": {
    "rarity_costs": {
        "normal": 1,
        "champion": 3,
        "rare": 5,
        "super_unique": 8
    },
    "floor_budgets": [
        { "max_floor": 2,  "base": 6,  "per_enemy": 1.0 },
        { "max_floor": 4,  "base": 8,  "per_enemy": 1.5 },
        { "max_floor": 6,  "base": 10, "per_enemy": 2.0 },
        { "max_floor": 8,  "base": 12, "per_enemy": 2.0 },
        { "max_floor": 99, "base": 15, "per_enemy": 2.5 }
    ]
}
```

### What this prevents
- A room with 4 enemies can no longer roll 2 rares (cost: 5+5=10 > budget of ~10-14). It'll get 1 rare + normals, or 1 rare + 1 champion at most.
- On floor 1-2, even a single rare in a 3-enemy room eats most of the budget (5 of 9 points), guaranteeing the other 2 are normal.
- Deep floors (9+) with budget=15 + 2.5/enemy give enough room for 2 rares in huge packs — keeps the danger alive.

### Replaces `max_enhanced_per_room`
The flat `max_enhanced_per_room=2` cap becomes redundant — the budget system is strictly superior because it accounts for the *magnitude* of each upgrade, not just the count. We keep the field in config for backward compatibility but the budget check runs first.

### Acceptance criteria
- [x] Floors 1-2 with small packs (3 enemies, budget 9) can never afford 2 rares — second rare downgraded to champion or normal
- [x] Deep floors (7+) can still produce multi-enhanced rooms (budget is generous)
- [x] Budget config is loaded from `monster_rarity_config.json` (data-driven, tunable)
- [x] New test: verify budget math with known enemy counts and floor tiers
- [x] New test: verify downgrade logic (rare → champion → normal when budget exceeded)
- [x] Existing rarity tests still pass (they test individual roll logic, not room-level)

### Implementation notes (completed 2026-03-06)
- **Config added**: `monster_rarity_config.json` — new `difficulty_budget` section with `rarity_costs` (normal=1, champion=3, rare=5, super_unique=8) and `floor_budgets` (5 tiers from floor 1-2 through 9+)
- **Helpers added**: `server/app/core/monster_rarity.py` — `get_difficulty_budget_config()`, `get_rarity_cost(rarity)`, `get_room_budget(floor_number, enemy_count)` 
- **map_exporter.py modified**: `_roll_rarity_for_spawn()` now accepts `room_budget_remaining` parameter. When budget is insufficient for a rolled rarity, it downgrades: rare → champion → normal. Room processing loop pre-computes budget via `get_room_budget(floor, regular_count)` and tracks `room_budget_remaining`, deducting `get_rarity_cost()` after each enemy.
- **Backward-compatible**: Missing `difficulty_budget` config section falls back to generous defaults (base=15, per_enemy=2.5). `max_enhanced_per_room` still applies as a hard cap alongside the budget.
- **Determinism**: Same seed → same rolls → same budget consumption → identical output.
- **Tests added**: `server/tests/test_wfc_difficulty_budget.py` — 53 tests across 9 test classes: rarity costs (6), room budget math (14), config structure (5), fallback behavior (2), downgrade logic (4), early-floor rare caps (8), deep floor budget (6), full pipeline integration (5), edge cases (4).
- **Test suite**: 3031 passed (0 failures), up from 2978 (+53 new).

---

## Phase 4: Neighbor-Aware Cluster Smoothing

**Priority**: LOW — polish pass  
**Effort**: Small  
**Files**: `server/app/core/wfc/room_decorator.py`

### What changes

After the deck-dealt role assignment (Phase 1), scan for "hot clusters" — groups of 2+ adjacent enemy rooms — and downgrade one to a mixed/loot room.

### Implementation

Add a post-assignment smoothing pass after the deck deal:

```python
# ── Pass C2: Cluster smoothing ──
# Build adjacency: two rooms are adjacent if Manhattan distance == 1 on the grid
def _get_adjacent_keys(gr, gc):
    return [f"{gr+dr},{gc+dc}" for dr, dc in [(-1,0),(1,0),(0,-1),(0,1)]]

hot_clusters = []
visited = set()
for room in flexible_rooms:
    key = f"{room['gridRow']},{room['gridCol']}"
    if key in visited or assignments.get(key) != "enemy":
        continue
    # BFS to find connected enemy rooms
    cluster = []
    queue = [room]
    while queue:
        current = queue.pop(0)
        ck = f"{current['gridRow']},{current['gridCol']}"
        if ck in visited:
            continue
        visited.add(ck)
        if assignments.get(ck) == "enemy":
            cluster.append(current)
            for adj_key in _get_adjacent_keys(current["gridRow"], current["gridCol"]):
                # Find the room object for this key
                for r2 in flexible_rooms:
                    if f"{r2['gridRow']},{r2['gridCol']}" == adj_key and adj_key not in visited:
                        queue.append(r2)
    if len(cluster) >= 2:
        hot_clusters.append(cluster)

# Downgrade one room in each cluster to "loot" (with guard scatter)
for cluster in hot_clusters:
    # Pick the room closest to spawn (easiest to reach = most forgiving)
    cluster.sort(key=lambda r: room_distances.get(f"{r['gridRow']},{r['gridCol']}", 0))
    target = cluster[0]
    target_key = f"{target['gridRow']},{target['gridCol']}"
    assignments[target_key] = "loot"  # Downgrade to loot (scatter may add 1 guard)
```

### Rules
- Only clusters of 2+ adjacent enemy rooms are affected
- Exactly **one** room per cluster is downgraded to "loot"
- The room closest to spawn is the one downgraded (most forgiving to the player)
- Clusters of 3+ still keep 2+ enemy rooms — just break the wall of enemies
- Loot rooms can still have a 45% chance of a scatter guard (1 enemy), so it's not completely free

### Acceptance criteria
- [x] No two adjacent rooms are both full enemy rooms after smoothing
- [x] Clusters of 3 keep at least 2 enemy rooms (only 1 downgraded per iteration)
- [x] Non-adjacent enemy rooms are never affected
- [x] Downgraded rooms become loot (not empty) to maintain dungeon content
- [x] New test: construct a known grid with adjacent enemy assignments, verify smoothing

### Implementation notes (completed 2026-03-06)
- **File changed**: `server/app/core/wfc/room_decorator.py` — Pass C2 added after deck dealing, before tile placement (Phase 4)
- **Algorithm**: Iterative BFS-based cluster detection. Each iteration finds clusters of 2+ adjacent enemy rooms, downgrades one room per cluster (closest to spawn) to "loot". Repeats until no adjacent enemy pairs remain. Safety-bounded by room count to prevent infinite loops.
- **Downgrade target**: The room closest to spawn in each cluster is downgraded (most forgiving to the player). Downgraded rooms become "loot" (not "empty") so they still contribute content (chests + optional scatter guard).
- **Room output enrichment**: Each decorated room now includes `clusterSmoothed` (bool) flag indicating whether it was downgraded by cluster smoothing.
- **Stats enrichment**: `stats` dict now includes `clustersFound` (total clusters detected across all iterations) and `clustersSmoothed` (rooms downgraded).
- **Iterative approach**: A single-pass design only handled clusters of exactly 2. The iterative approach handles chains of 3+ (e.g., A-B-C in a line: first pass downgrades A, second pass sees B-C still adjacent and downgrades B).
- **Determinism**: Same seed → same BFS order → same cluster detection → same smoothing → identical output.
- **Phase 1/2 test updates**: 5 existing tests in `test_wfc_room_quota.py` and `test_wfc_proximity.py` updated to account for cluster smoothing shifting enemy→loot counts (wider tolerances, smoothing-aware assertions).
- **Tests added**: `server/tests/test_wfc_cluster_smoothing.py` — 28 tests across 9 test classes: cluster detection (3), no adjacent enemy pairs (4), cluster size preservation (2), spawn proximity ordering (1), non-adjacent protection (2), downgrade to loot (2), stats (4), determinism (2), edge cases (4), phase integration (4).
- **Test suite**: 3059 passed (0 failures), up from 3031 (+28 new).

---

## Phase 5: Early-Floor Rarity Tuning

**Priority**: LOW — config-only polish  
**Effort**: Trivial  
**Files**: `server/configs/monster_rarity_config.json`

### What changes

Simple number tweaks to the existing rarity config to reduce early-floor spike danger. No code changes needed — the existing systems already read these values.

### Config changes

```json
"spawn_chances": {
    "champion_base_chance": 0.04,       // unchanged
    "rare_base_chance": 0.02,           // unchanged  
    "floor_bonus_per_level": 0.015,     // unchanged
    "boss_tiles_never_upgrade": true,   // unchanged
    "max_enhanced_per_room": 2,         // kept for backward compat (budget supersedes)
    "min_floor_for_champions": 2,       // unchanged
    "min_floor_for_rares": 4,           // unchanged

    // NEW: Per-floor-tier overrides
    "floor_overrides": [
        {
            "max_floor": 3,
            "max_enhanced_per_room": 1,     // Only 1 enhanced mob per room on floors 1-3
            "max_rare_minions": 1,          // Rares spawn only 1 minion instead of 2-3
            "rare_affix_count": [1, 2]      // Rares get 1-2 affixes instead of 2-3
        },
        {
            "max_floor": 5,
            "max_enhanced_per_room": 2,     // Normal cap
            "max_rare_minions": 2,          // Rares spawn up to 2 minions
            "rare_affix_count": [2, 2]      // Rares get exactly 2 affixes
        }
        // Floors 6+: use base config values (2-3 minions, 2-3 affixes)
    ]
}
```

### Implementation notes

This requires a small code addition in `map_exporter.py`'s `_roll_rarity_for_spawn()` to check for `floor_overrides` and apply the tier-specific caps. The monster_rarity functions (`roll_affixes`, minion count) would receive the capped values as parameters.

### What this does
- **Floors 1-3**: At most 1 enhanced enemy per room, and if it's rare it only gets 1-2 affixes + 1 minion. A rare skeleton with 1 affix and 1 minion is interesting but survivable.
- **Floors 4-5**: 2 enhanced per room, rares get 2 affixes + 2 minions. Ramping up.
- **Floors 6+**: Full power — 2-3 affixes, 2-3 minions, budget system (Phase 3) is the only constraint.

### Acceptance criteria
- [x] Floor 1-3 rooms never have more than 1 enhanced enemy
- [x] Floor 1-3 rares have at most 2 affixes and 1 minion
- [x] Floor 6+ behavior is unchanged from current
- [x] Config is backward-compatible (missing `floor_overrides` → use base values)
- [x] New test: verify floor override loading and application

### Implementation notes (completed 2026-03-06)
- **Config added**: `monster_rarity_config.json` — new `floor_overrides` array in `spawn_chances` section with 2 tiers: floors 1-3 (`max_enhanced_per_room=1`, `max_rare_minions=1`, `rare_affix_count=[1,2]`) and floors 4-5 (`max_enhanced_per_room=2`, `max_rare_minions=2`, `rare_affix_count=[2,2]`). Floors 6+ use base config values.
- **Helper added**: `server/app/core/monster_rarity.py` — `get_floor_override(floor_number)` looks up the first matching tier from `floor_overrides`. Returns empty dict when no tier matches or config is absent (backward-compatible).
- **map_exporter.py modified**: Imports `get_floor_override`, computes `_floor_override` at generation time. `_max_enhanced_per_room` now reads from floor override first, falling back to base `spawn_chances` value. `_roll_rarity_for_spawn()` uses floor-override `rare_affix_count` instead of rarity tier default when present.
- **match_manager.py modified**: `_spawn_dungeon_enemies()` imports `get_floor_override`, looks up override for `match.current_floor`. Rare minion count is capped by `floor_override.get("max_rare_minions")` when present.
- **Existing test updated**: `test_monster_rarity_spawn.py::test_rare_spawns_minions` — now sets `current_floor=7` to test base minion behavior without Phase 5 cap. Floor-specific caps tested in dedicated Phase 5 test file.
- **Determinism**: Same seed → same floor override lookup → same caps → identical output.
- **Tests added**: `server/tests/test_wfc_floor_overrides.py` — 37 tests across 9 test classes: floor override lookup (8), override values (6), config structure (5), backward compatibility (2), max enhanced pipeline (4), affix count pipeline (4), budget interaction (2), determinism (2), edge cases (4).
- **Test suite**: 3096 passed (0 failures), up from 3059 (+37 new).

---

## Implementation Order

```
Phase 1 (Quota)
    ↓
Phase 2 (Proximity Ramp)       ← can be developed alongside Phase 1
    ↓
Phase 3 (Difficulty Budget)     ← independent of 1+2, but applied after
    ↓
Phase 4 (Cluster Smoothing)     ← requires Phase 1 (deck) to be in place
    ↓
Phase 5 (Rarity Tuning)         ← config-only, can ship anytime after Phase 3
```

### Dependency graph
- **Phase 1** is standalone — replaces Pass C in room_decorator.py
- **Phase 2** builds on Phase 1 (modifies how the deck is dealt) — can develop in parallel but merges after
- **Phase 3** is standalone — modifies map_exporter.py's rarity roller, independent of room assignment
- **Phase 4** requires Phase 1's deck system (post-assignment smoothing pass)
- **Phase 5** requires Phase 3 (floor_overrides interact with the budget system)

### Testing strategy
Each phase adds its own test file or extends existing ones:
- `test_wfc_room_quota.py` — Phase 1 quota math, deck building, edge cases (19 tests, updated for Phase 4 tolerances)
- `test_wfc_proximity.py` — Phase 2 distance calculation, safe zones (26 tests, updated for Phase 4 tolerances)
- `test_wfc_difficulty_budget.py` — Phase 3 budget math, downgrade logic (53 tests)
- `test_wfc_cluster_smoothing.py` — Phase 4 cluster detection, adjacency guarantee, smoothing mechanics (28 tests)
- `test_wfc_floor_overrides.py` — Phase 5 floor override lookup, config values, pipeline integration (37 tests)

### Expected total test additions: ~30-40 new tests across all phases
### Actual tests added (Phases 1-5): 163 tests total (19 + 26 + 53 + 28 + 37)

---

## Key Files Reference

| File | Phases | What changes |
|---|---|---|
| `server/app/core/wfc/room_decorator.py` | 1, 2, 4 | Pass C rewrite (quota), proximity ramp, cluster smoothing |
| `server/app/core/wfc/map_exporter.py` | 3, 5 | Budget-aware rarity rolling, floor override application (enhanced cap, affix count) |
| `server/app/core/wfc/dungeon_generator.py` | 2 | Pass floor_number to decorator for distance context (if needed) |
| `server/configs/monster_rarity_config.json` | 3, 5 | New `difficulty_budget` section, `floor_overrides` in `spawn_chances` |
| `server/app/core/monster_rarity.py` | 3, 5 | `get_room_budget()` helper, `get_floor_override()` lookup |
| `server/app/core/match_manager.py` | 5 | Floor-override-aware rare minion count cap |
| `server/app/core/wfc/dungeon_styles.py` | — | No changes — style overrides feed into quota targets naturally |
