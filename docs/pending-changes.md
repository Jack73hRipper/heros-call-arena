# Pending Changes

> **Purpose:** AI agents and developers log changes here as they work.  
> When it's time to publish, clear this file after transferring entries  
> into `build/patch-notes.md` and `docs/changelog.md`.

---

## Unreleased

### Bug Fixes

- **Leader explore_room ↔ patrol_move oscillation reduced** — Team leaders would alternate between `explore_room` (pathing toward an unexplored room entrance) and `patrol_move` (waypoint-based scouting) on consecutive turns. When `explore_room` proposed a step back toward a tile the leader had just left, the two systems fought over direction: explore pulled east, patrol pulled west, creating sustained A→B→A bouncing across 2-3 tiles. The `explore_room` code path in `_decide_aggressive_action()` now checks the leader's `_position_history` before returning a MOVE: if the proposed next step matches the leader's position from last turn, the move is skipped and the leader falls through to patrol (which already has its own anti-backtrack guard via Option B). This prevents explore_room from pulling the leader backward, while patrol handles forward progress.
  - **Impact (seed 100, 150 turns):** `explore_room` ↔ `patrol_move` oscillation pairs dropped from 22 → 13 (**-41%**). Overall oscillation rate dropped from 12.0% → 9.2% (**-2.8pp**). Leaders now make 4x more productive moves (`explore_room` 33 → 131, `patrol_move` 51 → 135) instead of being stuck in suppression WAITs.
  - **Impact (seed 42, 100 turns):** Total oscillation events dropped from 112 → 70 (**-37%**). Oscillation rate dropped from 9.1% → 7.0%.
  - **File:** `server/app/core/ai_behavior.py` — `_decide_aggressive_action()`, strategic exploration block (4e)

- **Follower trail-moving oscillation eliminated** — When a team leader was moving, followers within distance 1 would trigger the `follow_trail_moving` tether and path toward the leader. In corridors and doorway chokepoints, multiple followers competing for the same 2-3 adjacent tiles caused the A* occupied set to shift each tick, sending followers back to their previous position (`A→B→A` cycle). The `follow_trail_moving` code path now checks the follower's position history before returning a MOVE: if the proposed next step is the tile the follower occupied last turn, the move is skipped and the follower falls through to idle/chest-seek behavior, breaking the cycle.
  - **Impact (seed 100, 150 turns):** `follow_trail_moving` ↔ `follow_trail_moving` oscillations dropped from 61 → 2 (**97% reduction**). `stall_breaker_yield` WAITs dropped from 222 → 144 (**-35%**). `oscillation_suppressed` WAITs dropped from 96 → 29 (**-70%**). Overall oscillation rate dropped from 13.8% → 12.0%. `follow_trail_moving` actions reduced from 341 → 87 (**-74%**) as backtrack moves are now rejected.
  - **File:** `server/app/core/ai_stances.py` — `_decide_follow_action()`, leader-is-moving tether block

- **Explore suppression tuned to reduce false-positive stalling** — The oscillation detection system was suppressing `explore_room` too aggressively, causing leaders to fall back to `patrol_move` and `random_adjacent_move` for 95%+ of their decisions. Three thresholds were relaxed:
  - **A↔B cycle detection** — History requirement raised from 6 to 8 consecutive positions with ≤2 unique tiles. Brief reversals during doorway/corridor navigation no longer trigger suppression.
  - **Broad stall bounding box** — History requirement raised from 8 to 12 positions, and bounding box tightened from ≤3 to ≤2 tiles. Only truly stuck patterns (12+ turns in a 2×2 area) trigger suppression.
  - **Suppression cooldown** — Minimum suppression duration reduced from 20 to 10 turns. Leaders re-engage exploration sooner after patrol breaks them out of the stuck area.
  - **Suppression lift distance** — Centroid distance gate reduced from 5 to 3 Manhattan tiles. Leaders don't need to travel as far before exploring again.
  - **Position history** — `_POSITION_HISTORY_LEN` increased from 8 to 12 to accommodate the longer detection windows.
  - **Impact (seed 42):** `explore_room` decisions increased from 8 to 30 per match (3.75x). `aggro_chest_seek` appeared 13 times (was 0). Door openings tripled (1 → 3). `random_adjacent_move` eliminated entirely.
  - **File:** `server/app/core/ai_behavior.py` — oscillation detection block, suppression lift block, constants

- **Patrol fallback now steps toward unexplored rooms instead of randomly** — When `_random_adjacent_move` fires (patrol has no waypoint / A* fails / back-step rejection), it now accepts an optional `exploration_hint` target. For team leaders, this is set to the nearest unexplored room entrance from `get_next_exploration_target()`. The function picks the adjacent tile closest to that target (Manhattan distance) instead of a random walkable tile. Non-leader units and enemies retain random fallback behavior.
  - **Impact:** All 10 previous `random_adjacent_move` instances replaced by 27 `directed_adjacent_move` with purposeful direction toward unexplored territory.
  - **Files:** `server/app/core/ai_patrol.py` — `_random_adjacent_move()` accepts `exploration_hint`, `_patrol_action()` accepts and threads `exploration_hint`; `server/app/core/ai_behavior.py` — builds exploration hint from `get_next_exploration_target()` before calling `_patrol_action()`

- **purge_unwanted_items() now respects weapon class-lock and armor affinity** — The item purge system previously scored items with raw `score_item_for_role()` without checking whether team members could actually equip them. A melee weapon could appear as an "upgrade" for a Mage (who can't equip it), preventing it from being purged for the correct recipient. Now mirrors the same class-lock and armor affinity gates used by `find_best_party_recipient()`.
  - **File:** `server/app/core/equipment_manager.py` — `purge_unwanted_items()` inner loop

- **Leader promotion now works for all AI team prefixes** — When a team leader died in PVPVE matches, the promotion logic in `deaths_phase.py` only triggered for units with the `"pvpve-ai-"` ID prefix. Team A heroes (spawned via `_spawn_ai_units()`) use the `"ai-"` prefix, so their leader's death would orphan all remaining followers — they'd enter `follow_no_owner` state and WAIT indefinitely for the rest of the match. The prefix check now accepts both `"pvpve-ai-"` and `"ai-"` prefixed units.
  - **Impact:** Eliminated 232 wasted `follow_no_owner` WAITs per 10-match sample (concentrated in matches where Team A's leader died early).
  - **File:** `server/app/core/turn_phases/deaths_phase.py` — leader promotion block

- **Oscillation suppression no longer fires on simple movement reversals** — The anti-oscillation system was converting any A→B→A movement pattern into an immediate WAIT, even on Turn 2 when followers and leaders compete for the same spawn tiles. Now a single reversal only clears the stale patrol waypoint. The WAIT (`oscillation_suppressed`) only triggers when extended criteria are confirmed: 6+ positions with ≤2 unique tiles (stuck A↔B cycle), or 8+ positions within a ≤3-tile bounding box (room shuffling).
  - **Impact:** Reduced hero `oscillation_suppressed` WAITs from 1,653 to 757 per 10-match sample (54% reduction). Overall hero WAIT rate dropped from ~15% to ~11%.
  - **File:** `server/app/core/ai_behavior.py` — oscillation detection block

- **Displaced equipment no longer strands in inventory after auto-equip** — When an AI hero picked up loot and `try_auto_equip` upgraded a slot, the displaced item (old weapon/armor/accessory) was placed back in inventory. `purge_unwanted_items` correctly detected it was an upgrade for a teammate and kept it — but no code ever transferred it to that teammate. Added a **redistribution pass** (Phase 28I) that runs after all auto-equip operations: scans every team member's inventory for equippable items, finds the best party recipient via `find_best_party_recipient()`, transfers the item, and triggers auto-equip on the recipient. Runs up to 3 cascading passes to handle chain upgrades (Hero A's old item upgrades Hero B, whose displaced item upgrades Hero C). Purge now also covers all team members, not just the picker and direct trade recipients.
  - **Impact (seed 42, 1 match):** Stranded upgrades dropped from 22 to 0. Items traded per match increased from 5 to 31. Items auto-equipped increased from 6 to 28. Items purged (freed inventory) increased from 11 to 31. Equipment health score improved from 75 to 95.
  - **Impact (seed 42, 5 matches):** Average stranded upgrades dropped from ~41 to ~3 per match. Total items traded tripled (26 → 94). Total items purged more than doubled (53 → 123). Average equipment health score improved from ~72 to 91.2.
  - **File:** `server/app/core/turn_phases/interaction_phase.py` — redistribution loop after auto-equip, expanded purge scope

### New Features

- **PVPVE Batch Tool: Equipment Management Report** — New `--equipment-report` flag for `batch_pvpve.py` that tracks and reports on all AI hero equipment management behavior. Includes:
  - **Spawn Gear Summary** — Equipment and potion counts for every hero at match start  
  - **Equipment Events** — Counts of items picked up, traded, auto-equipped, purged, potions shared/consumed, scavenge moves
  - **Per-Team Breakdown** — All event counts split by team
  - **Final Gear** — End-of-match equipment state with upgrade tracking (spawn vs final comparison)
  - **Potion Economy** — Start vs end potion counts, per-hero distribution, balance check
  - **Diagnostics** — Detects weapon class-lock violations, armor affinity mismatches, inventory overflow
  - **Health Score (0-100)** — Automated scoring of equipment system correctness (now penalizes stranded upgrades)
  - **Inventory Contents** — Shows every equippable item in each surviving hero's bag with score vs equipped (upgrade/sidegrade/downgrade)
  - **Stranded Upgrades** — Detects items in Hero A's bag that would be an upgrade for Hero B (or self), with exact delta values and recipient names
  - **Batch Summary** — Aggregated stats across multiple matches when running `--matches N` (now includes stranded upgrade totals)
  - Usage: `python batch_pvpve.py --equipment-report` or `python batch_pvpve.py --matches 10 --equipment-report`
  - **File:** `server/batch_pvpve.py` — Added `EquipmentTracker` class, `render_equipment_report()`, `--equipment-report` CLI flag, inventory contents section, stranded upgrades detection

- **Dev Overlay: Equipment & Inventory Inspector** — When inspecting a unit in dev mode (backtick → Inspect ON → click unit), the panel now shows full equipment and inventory data:
  - **Equipment section** (collapsible) — Displays Weapon, Armor, and Accessory slots with item name, rarity (color-coded: Common/Magic/Rare/Epic/Unique/Set), weapon/armor category, stat bonuses, affix names, and set membership. Empty slots shown as "— empty —".
  - **Inventory section** (collapsible) — Scrollable list of all bag items (capacity X/10) with rarity colors. Consumables marked with ⚗ icon.
  - **Works on ALL units** — Not limited to party members. Can inspect AI hero loadouts, enemy equipment, boss gear, and any unit in the match via a new `dev_get_unit_inventory` server endpoint that bypasses party-membership checks (requires dev mode enabled).
  - **Auto-refresh** — Inventory data automatically fetches on inspect and refreshes every 3 seconds, so you can watch AI heroes equip/swap gear in real time.
  - **Files changed:**
    - `server/app/core/equipment_manager.py` — Added `dev_get_unit_inventory()` function
    - `server/app/core/match_manager.py` — Re-exported `dev_get_unit_inventory`
    - `server/app/services/message_handlers.py` — Added `handle_dev_get_unit_inventory` handler + dispatch entry
    - `client/src/App.jsx` — Added `dev_unit_inventory` WS message routing
    - `client/src/hooks/useDevOverlay.js` — Added inventory state, auto-fetch on inspect, periodic refresh
    - `client/src/components/DevOverlay/DevOverlayPanel.jsx` — Added equipment/inventory UI sections with rarity colors, stat display, collapsible panels
    - `client/src/components/Arena/Arena.jsx` — Passed `inspectedInventory` prop to DevOverlayPanel
    - `client/src/styles/components/_dev-overlay.css` — Added 160+ lines of new styles for equipment/inventory display

- **Oscillation suppression deadlock broken — hard timeout prevents permanent freeze** — The oscillation suppression system had a circular deadlock: when a leader was detected as oscillating, `_explore_suppressed` was set and the action was forced to `WAIT("oscillation_suppressed")`. However, the suppression *lift* condition required `action.action_type == ActionType.MOVE` — but since the action was always WAIT while suppressed, the condition could never be met. Leaders would enter suppression and never recover, freezing the entire team for 150+ turns. Added a hard timeout (`_MAX_SUPPRESS_TURNS = 30`) that unconditionally lifts suppression after 30 ticks regardless of action type. The timeout also clears `_visited` history so patrol gets fresh waypoint candidates on resume. The original MOVE-based lift (Path A) still works for cases where the leader naturally moves during suppression.
  - **Impact (seed 42, 200-turn trace):** Leader decisions increased from 22 to 145 (6.6× improvement). Leaders now actively explore throughout the match instead of freezing at turn ~32.
  - **Impact (seed 42, 5-match batch):** Items picked up increased from 54 to 74 (+37%). Items traded increased from 51 to 77 (+51%). Movement decisions increased from 3296 to 3782+.
  - **File:** `server/app/core/ai_behavior.py` — suppression lift block, added `_MAX_SUPPRESS_TURNS = 30` constant and Path B unconditional timeout lift

- **Patrol waypoint scoring no longer deadlocks when all tiles are visited** — `_pick_patrol_waypoint()` applies a −15.0 penalty to any candidate tile in the `_visited` set. When all walkable candidates have been visited (common on smaller maps or after thorough exploration), every tile receives the penalty equally, making the scoring degenerate and sometimes returning no viable waypoint. The function now detects when all candidates are visited and disables the visited penalty for that selection, allowing the patrol system to pick the best non-visited-penalized waypoint and continue moving.
  - **File:** `server/app/core/ai_patrol.py` — `_pick_patrol_waypoint()`, `all_visited` check before scoring loop

- **Followers now auto-explore when leader is idle** — When a team leader is stationary for 5+ consecutive ticks (checked via `_position_history`), followers in follow stance would WAIT indefinitely with `follow_idle`. Now they make a random adjacent move (`follow_autonomous_wander`) instead, keeping the team active even during temporary leader stalls. This prevents the cascade where a stuck leader freezes the entire team.
  - **File:** `server/app/core/ai_stances.py` — `_decide_follow_action()`, Phase 31 autonomous follower exploration block before final `follow_idle` return

### Balance Changes

*(none yet)*

### Known Issues

- On XL maps (64×64, grid-size 8), the 300-turn limit is often insufficient for 4 teams to explore the dungeon and encounter each other, resulting in high draw rates. This is a map-size/turn-limit design consideration rather than an AI behavior bug — teams are actively exploring throughout the match.

- Lobby chat between connected players not yet working — investigation in progress.
