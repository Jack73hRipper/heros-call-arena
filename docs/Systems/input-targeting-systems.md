# Input, Auto-Attack, Auto-Spell & Targeting Systems

> **Purpose**: Living reference for how player inputs, targeting, auto-attack, and auto-spell systems work together. Created to support QoL improvements.

---

## Table of Contents
1. [System Overview](#1-system-overview)
2. [Input Layer (Client)](#2-input-layer-client)
3. [Action Modes & Highlights](#3-action-modes--highlights)
4. [Targeting System](#4-targeting-system)
5. [Auto-Target (Auto-Attack & Auto-Spell)](#5-auto-target-auto-attack--auto-spell)
6. [Action Queue](#6-action-queue)
7. [Server Tick & Turn Resolution](#7-server-tick--turn-resolution)
8. [Full Flow Diagrams](#8-full-flow-diagrams)
9. [Key State Variables](#9-key-state-variables)
10. [File Reference](#10-file-reference)

---

## 1. System Overview

The game uses a **tick-based** (1s default) action queue model. Each tick, one action per unit is popped from its queue and fed into a 10-phase turn resolver. When the queue is empty and an auto-target is set, the server generates an action automatically (move toward, attack, or cast skill).

```
┌─────────────────────────────────────────────────────────────┐
│                      CLIENT INPUTS                          │
│  WASD/Arrows │ Left-Click │ Right-Click │ Skill Hotkeys 1-5│
└──────┬───────┴─────┬──────┴──────┬──────┴───────┬──────────┘
       │             │             │              │
       ▼             ▼             ▼              ▼
  ┌──────────┐ ┌───────────┐ ┌──────────┐ ┌────────────┐
  │batch_    │ │action     │ │batch_    │ │action /    │
  │actions   │ │(single)   │ │actions + │ │set_auto_   │
  │(1 move)  │ │OR target  │ │set_auto_ │ │target      │
  │          │ │select     │ │target    │ │(+skill_id) │
  └────┬─────┘ └─────┬─────┘ └────┬─────┘ └─────┬──────┘
       │              │            │              │
       ▼              ▼            ▼              ▼
  ┌───────────────── SERVER ─────────────────────────┐
  │                  ACTION QUEUE                     │
  │    [action1] [action2] ... [actionN]              │
  │          ↕ mutually exclusive ↕                   │
  │              AUTO-TARGET                          │
  │    { target_id, skill_id? }                       │
  └────────────────────┬─────────────────────────────┘
                       │ each tick: pop 1 action
                       ▼
  ┌─────────────── TURN RESOLVER ────────────────────┐
  │  Phase 0:   Items (potions)                       │
  │  Phase 0.5: Cooldowns & Buffs                     │
  │  Phase 1:   Movement (cooperative batch)          │
  │  Phase 1.5: Doors (interact)                      │
  │  Phase 1.75: Loot (chests + ground items)         │
  │  Phase 1.9: Skills                                │
  │  Phase 2:   Ranged Attacks                        │
  │  Phase 3:   Melee Attacks                         │
  │  Phase 3.5: Deaths + Loot Drops                   │
  │  Phase 4:   Victory Check                         │
  └──────────────────────────────────────────────────┘
```

---

## 2. Input Layer (Client)

### 2.1 WASD / Arrow Keys (`useWASDMovement.js`)

Roguelike-style continuous movement. Hold two keys for diagonals (W+D = northeast).

| Behavior | Detail |
|----------|--------|
| **Model** | "Replace, not stack" — only ONE WASD move is ever queued at a time |
| **Direction change** | Replaces the queued move instantly via `batch_actions` |
| **After tick resolves** | If keys still held, auto-queues the next step (continuous walk) |
| **Release all keys** | Leaves the last move queued (tap-and-release works) |
| **Modifier keys** | Disabled when Ctrl/Alt/Meta held (those are for party shortcuts) |
| **Server message** | `batch_actions` with a single move action (atomic clear + queue) |

### 2.2 Left-Click (`useCanvasInput.js` → `handleCanvasClick`)

Context-sensitive based on what's clicked and whether an action mode is active:

| Click Target | Modifier | Action Mode Active? | Result |
|-------------|----------|--------------------|---------| 
| **Party member** | None | No | `SELECT_TARGET` — soft-select for healing/skill targeting |
| **Party member** | Shift | No | Toggle multi-select (`select_party_member` / `release_party_member`) |
| **Party member** | Ctrl | No | Take direct control of that party member |
| **Self** | None | No | Return to controlling self, deselect all party members |
| **Empty tile** | None | No | Deselect all units + clear selected target |
| **Enemy unit** | None | No | `SELECT_TARGET` — soft-select as target |
| **Valid tile** | None | `move` | Queue move action (stays in move mode for multi-queue) |
| **Enemy tile** | None | `attack` | Queue melee attack action |
| **Enemy tile** | None | `ranged_attack` | Queue ranged attack action |
| **Valid tile** | None | `interact` | Queue interact action (door toggle) |
| **Valid tile** | None | `skill_<id>` | Queue skill action with target |

**Important**: Any manual left-click action clears `autoTargetId` on the client immediately.

### 2.3 Right-Click (`useCanvasInput.js` → `handleContextMenu`)

Smart context-sensitive pathfinding — the primary way players interact with the world:

| Target Tile Content | Intent | Actions Generated |
|---|---|---|
| **Enemy unit** | `attack` | A* path to adjacent tile + melee attack + `set_auto_target` |
| **Closed door** | `interact` | A* path to adjacent tile + interact |
| **Unopened chest** | `loot_chest` | A* path to adjacent tile + loot |
| **Ground items** | `loot` | A* path onto the tile + loot |
| **Empty tile** | `move` | A* path to the tile |
| **Queue tile** | `truncate` | Truncate queue to that point |

**Key right-click behaviors:**
- Sends `batch_actions` (replaces entire queue)
- Right-clicking an enemy also sends `set_auto_target` for persistent pursuit
- Right-clicking anything else sends `clear_auto_target`
- Group right-click (multiple units selected): each unit gets independent A* path + auto-target if enemy

### 2.4 Keyboard Shortcuts (`useKeyboardShortcuts.js`)

| Key | Action |
|-----|--------|
| **Tab** | Cycle `selectedTargetId` through visible enemies (nearest-first) (QoL-D) |
| **Shift+Tab** | Cycle `selectedTargetId` in reverse (farthest-first) (QoL-D) |
| **1-5** | Activate skill (same as clicking skill button) |
| **Ctrl+A** | Select all party members |
| **F1-F4** | Select individual party member by index |
| **Ctrl+1-4** | Set stance (follow / aggressive / defensive / hold) |
| **Escape** | Clear queue + clear auto-target + clear action mode + clear selected target |

### 2.5 Skill Hotkeys & Buttons (`BottomBar.jsx`)

The skill click handler (`handleSkillClick`) has four paths:

| Path | Condition | Behavior |
|------|-----------|----------|
| **A — Self-cast** | Skill targeting = `self` | Immediately queues skill action (no targeting needed) |
| **B — Target-first** | `selectedTargetId` is set + valid for the skill | In range + off cooldown → cast immediately. Otherwise → `set_auto_target` with `skill_id` for auto-pursue-and-cast |
| **B′ — Auto-select nearest** | No pre-selected target + visible enemies/allies exist | Finds the nearest valid target (enemy for offensive, injured ally for heals), dispatches `SELECT_TARGET` to update HUD, then follows Path B logic (cast if in range, otherwise `set_auto_target` for pursuit). FOV-filtered. |
| **C — Targeting mode** | No pre-selected target AND no visible valid targets | Enters `actionMode = 'skill_<id>'`, player clicks a valid tile to cast |

> **QoL-H (Auto-Select Nearest Target)**: Path B′ eliminates the need to Tab-target or left-click an enemy before pressing a skill. The player can simply press a skill hotkey and the nearest valid target is auto-selected. Tab still works for manual target switching before pressing the skill.

---

## 3. Action Modes & Highlights

### 3.1 Action Mode State

`actionMode` is a string in the global game state, set via `SET_ACTION_MODE` dispatch.

| Value | Source | Visual |
|-------|--------|--------|
| `null` | Default / cleared | No highlights, right-click smart actions available |
| `'move'` | (Legacy, no button) | Blue adjacent tiles |
| `'attack'` | (Legacy, no button) | Red adjacent enemy tiles |
| `'ranged_attack'` | Ranged button | Red tiles within 5-tile Euclidean radius with enemies |
| `'interact'` | (Legacy, dungeon) | All door tiles highlighted |
| `'skill_<id>'` | Skill button / hotkey | Depends on skill targeting type |

### 3.2 Highlight Computation (`useHighlights.js`)

Highlights are computed via `useMemo` based on `actionMode` and unit position.

| Action Mode | Range | Valid Tiles |
|---|---|---|
| `move` | 1 tile (8-directional) | Not obstacle, not enemy-occupied. Allies allowed (server handles displacement) |
| `attack` | 1 tile (8-directional) | Only enemy-occupied tiles |
| `ranged_attack` | 5 tiles (Euclidean) | Only enemy-occupied tiles within range. No client-side LOS check (server validates) |
| `skill` — `self` | Own tile | Self only |
| `skill` — `ally_or_self` | Adjacent | Own tile + adjacent alive allies |
| `skill` — `enemy_adjacent` | 1 tile | Adjacent enemy-occupied tiles |
| `skill` — `enemy_ranged` | Skill range (Euclidean) | Enemies within range |
| `skill` — `empty_tile` | Skill range | Empty non-obstacle tiles |
| `interact` | Entire map | All door tiles |

### 3.3 Queue Preview & Hover Preview

- **Queue preview** (`queuePreviewTiles`): Walks the action queue simulating position changes, renders ghost-tiles typed by action (move/attack/skill/etc.)
- **Hover preview** (`hoverPreviews`): When no action mode is active, shows ghost A* paths to the hovered tile for all selected units (real-time feedback before right-clicking)

---

## 4. Targeting System

There are **two independent targeting concepts**:

### 4.1 `selectedTargetId` — Manual / Soft Target

The unit the player has left-clicked on. Used for:
- **HUD display**: Shows target name, HP bar, class
- **Skill target-first casting**: If a target is selected when a skill button is pressed, the skill tries to cast on that target (Path B in skill handler)
- **Visual indicator**: Target ring drawn on the unit

| How it's set | How it's cleared |
|---|---|
| Left-click any unit (enemy or ally) | Left-click empty tile |
| Right-click enemy (also sets auto-target) | Press Escape |
| | Enter an action mode (`SET_ACTION_MODE`) |

**Important**: `selectedTargetId` is **NOT** cleared by non-attack right-clicks (moving somewhere). This is intentional so the player doesn't lose their target when walking around.

### 4.2 `autoTargetId` — Auto-Pursuit Target

The unit being auto-attacked / auto-casted on. This is the **server-authoritative** pursuit target. When the action queue is empty, the server generates actions to pursue and attack/cast on this target.

| How it's set | How it's cleared |
|---|---|
| Right-click an enemy | Right-click anything else (move/interact/loot) |
| Skill button + out-of-range selected target → `set_auto_target` | Manual left-click action (any action mode click) |
| Group right-click enemy (sets for all selected units) | Press Escape |
| | Target dies (server clears + notifies client) |
| | Target becomes unreachable (A* failure, server clears) |
| | `batch_actions` sent (new queue replaces pursuit) |
| | `clear_queue` sent |

### 4.3 Relationship Between the Two

```
selectedTargetId (soft/UI)          autoTargetId (pursuit/server)
         │                                    │
         │  Independent — can coexist.        │
         │  Auto-target SET clears selected.  │
         │  Selected does NOT affect auto.    │
         │                                    │
         ▼                                    ▼
   HUD display                          Server-side action
   Skill target-first                   generation each tick
   Visual ring                          (move/attack/skill)
```

---

## 5. Auto-Target (Auto-Attack & Auto-Spell)

### 5.1 Server-Side: `auto_target.py`

#### Setting Auto-Target (`set_auto_target`)
- Validates: player alive, target alive, correct team (enemies for attacks, allies for heals)
- If `skill_id` provided: validates class can use the skill, targeting type is compatible
- **Clears the action queue** on success (pursuit replaces manual commands)
- Stores `player.auto_target_id` and `player.auto_skill_id`

#### Generating Actions (`generate_auto_target_action`)

Called once per tick for units with `auto_target_id` and an empty queue:

```
generate_auto_target_action(match_id, player_id, ...)
    │
    ├─ Validate target alive + correct team
    │   └─ Invalid → clear auto-target, return None
    │
    ├─ If auto_skill_id is set:
    │   │
    │   ├─ Compute effective range:
    │   │   ├─ enemy_adjacent → range 1 (Chebyshev)
    │   │   ├─ enemy_ranged → skill.range or player.ranged_range
    │   │   └─ ally_or_self → max(skill.range, 1)
    │   │
    │   ├─ In range + on cooldown → return WAIT
    │   ├─ In range + off cooldown + LOS blocked → return MOVE (reposition)
    │   ├─ In range + off cooldown + LOS ok → return SKILL action
    │   └─ Out of range → A* MOVE toward target
    │
    ├─ If no skill (melee pursuit):
    │   ├─ Adjacent → return ATTACK
    │   └─ Not adjacent → A* MOVE toward target
    │
    └─ A* fails → clear auto-target, return None
```

### 5.2 Auto-Target in the Tick Loop (`tick_loop.py`)

**Step 3.5** — After popping queued actions but before turn resolution:

```python
for each alive human/controlled unit with no queued action this tick:
    if unit.auto_target_id:
        auto_action = generate_auto_target_action(...)
        if auto_action:
            add to action_list for this tick
        elif target was cleared (died/unreachable):
            notify client: "auto_target_cleared" + reason
```

**Post-turn cleanup** — After the turn resolves:
```python
for each unit that died this turn:
    clear their queue + auto-target
    for every OTHER unit targeting the dead unit:
        clear their auto-target
        notify their owner: "auto_target_cleared", reason: "target_died"
```

**State sync** — Each `TURN_RESULT` payload includes current `auto_targets` map so the client stays in sync.

### 5.3 Client-Side Auto-Target State

| Reducer | State Keys | Purpose |
|---------|-----------|---------|
| `partyReducer` | `autoTargetId`, `autoSkillId` | Player's own auto-target |
| `partyReducer` | `partyAutoTargets`, `partyAutoSkills` | Party members' auto-targets |
| `combatReducer` | (TURN_RESULT sync) | Rebuilds auto-target state from server payload each tick |

### 5.4 HUD Display of Auto-Target

The HUD shows real-time pursuit status:

| State | Display |
|-------|---------|
| Auto-target with skill + out of range | "Approaching for \<Skill\>..." |
| Auto-target with skill + in range + off CD | "Casting \<Skill\>!" |
| Auto-target with skill + in range + on CD | "Cooldown (\<N\>)" |
| Auto-target melee + not adjacent | "Pursuing..." |
| Auto-target melee + adjacent | "Attacking!" |
| Selected target (no auto) | Target info frame with HP bar |
| No target | "No Target — Click a unit to select" |

---

## 6. Action Queue

### 6.1 Queue Model

- **Max size**: 10 actions (configurable)
- **Per-unit**: Each unit has its own independent queue
- **Pop model**: One action per unit per tick (FIFO)
- **Replace model**: `batch_actions` clears the queue first, then queues all new actions

### 6.2 Queue vs Auto-Target (Coexistent — QoL-A)

As of QoL-A, the queue and auto-target can coexist. The queue drains first;
auto-target only generates actions when the queue is empty.

| Event | Queue | Auto-Target |
|-------|-------|-------------|
| `set_auto_target` called | **Unchanged** (queue drains first) | **Set** |
| `batch_actions` called | **Filled** | **Unchanged** (not cleared) |
| `queue_action` (single) called | **Appended** | **Cleared** |
| `clear_queue` called | **Cleared** | **Cleared** |
| Queue has actions at tick | Action **consumed** (popped) | Auto-target **skipped** (unit already in `submitted_ids`) |
| Queue empty + auto-target set | N/A | `generate_auto_target_action()` fires |
| Non-attack right-click | **Filled** | **Cleared** (via explicit `clear_auto_target` message from client) |

### 6.3 Queue Messages

| WS Message | Purpose |
|---|---|
| `action` | Queue a single action (append) |
| `batch_actions` | Clear queue + queue multiple actions (right-click pathfinding) |
| `clear_queue` | Clear all queued actions |
| `remove_last` | Remove last queued action (undo) |
| `group_batch_actions` | Batch actions for multiple selected units at once |

---

## 7. Server Tick & Turn Resolution

### 7.1 Tick Loop Steps (`tick_loop.py` — `match_tick()`)

```
Step 1:  Calculate FOV for all units
Step 2:  Run AI decisions (enemies, uncontrolled party members)
Step 3:  Pop queued actions (one per unit)
Step 3.5: Generate auto-target actions for units with empty queues
Step 4:  Resolve all actions through turn_resolver.resolve_turn()
Step 5:  Handle wave spawner checks
Step 6:  Build per-player payloads (FOV-filtered)
Step 7:  Broadcast TURN_RESULT to all connected players
Step 8:  Post-turn cleanup (dead unit queues, auto-target cascading)
```

### 7.2 Turn Resolution Phases (`turn_resolver.py`)

| Phase | Name | Key Details |
|-------|------|-------------|
| **0** | Items | Potions consumed, HP restored |
| **0.5** | Cooldowns & Buffs | All cooldowns tick -1, DoT/HoT applied |
| **1** | Movement | Cooperative batch movement with swap/chain detection |
| **1.5** | Doors | INTERACT toggles door open/closed |
| **1.75** | Loot | Chest interaction + ground item pickup |
| **1.9** | Skills | `can_use_skill()` validation → `resolve_skill_action()` dispatch |
| **2** | Ranged Attacks | Entity-target resolution, LOS/range/cooldown validation, damage calc |
| **3** | Melee Attacks | Entity-target or tile-based, adjacency check, pre-move occupant tracking |
| **3.5** | Deaths | Loot drops, kill tracking, permadeath |
| **4** | Victory | Team or FFA victory check |

### 7.3 Attack Resolution Details

**Melee** (`_resolve_melee`):
- Entity-based targeting: resolves target by ID, checks adjacency to target's **current** position (after movement phase)
- Tile-based fallback: checks who is on the target tile
- Pre-move tracking: if original target moved away, checks if original occupant is still in melee range at new position
- Damage: `(base_atk + equip_bonus) * melee_buff_mult - armor` (min 1)

**Ranged** (`_resolve_ranged`):
- Entity-based targeting with tile fallback
- Validates via `can_ranged_attack()`: cooldown ready, Euclidean range ≤ 5, LOS clear
- Sets 3-turn cooldown on use
- Damage: `(base_ranged + equip_bonus) * ranged_buff_mult - armor` (min 1)

**Skills** (`_resolve_skills`):
- Validates via `can_use_skill()`: cooldown ready, range check, mana/resource check
- Dispatches to `resolve_skill_action()` which handles all skill types (damage, heal, buff, debuff, etc.)

---

## 8. Full Flow Diagrams

### 8.1 Right-Click Enemy → Auto-Attack Flow (QoL-A)

```
Player right-clicks on enemy
    │
    ├─ Client: generateSmartActions() — A* path to adjacent tile
    │          intent = 'attack'
    │          actions = [move, move, ..., attack]
    │
    ├─ Client sends: batch_actions { actions: [...] }
    │   └─ Server: clears queue, queues all actions from the A* path
    │      (auto-target NOT cleared — batch_actions no longer touches it)
    │      (queue_action clears any stale auto-target on first append,
    │       but set_auto_target re-sets it in the next message)
    │
    ├─ Client sends: set_auto_target { target_id: enemy_id }
    │   └─ Server: sets auto_target_id (queue NOT cleared — coexist)
    │
    │   Result: queue has full A* path, auto-target is set.
    │
    ├─ Ticks 1-6: queue pops one move per tick (client's optimal A* path)
    │             auto-target skipped (unit already in submitted_ids)
    │
    ├─ Tick 7: queue empty → auto-target generates ATTACK (adjacent)
    │
    ├─ Tick 8+: auto-target continues pursuit if enemy moves away
    │
    ├─ Enemy dies: server clears auto-target, notifies client
    │
    └─ Client dispatches: AUTO_TARGET_CLEARED, HUD updates
```

> **QoL-A** (implemented): The client's optimized A* path is now used for the initial approach. Auto-target only takes over when the queue is empty, providing seamless pursuit when the enemy moves.

### 8.2 Skill Target-First Flow

```
Player left-clicks enemy → SELECT_TARGET (selectedTargetId set)
    │
    ├─ Player presses skill hotkey (e.g., "2")
    │
    ├─ handleSkillClick checks:
    │   ├─ selectedTargetId is set ✓
    │   ├─ Target valid for skill targeting type ✓
    │   │
    │   ├─ In range + off cooldown?
    │   │   └─ YES → send action { type: 'skill', skill_id, target_id }
    │   │
    │   └─ Out of range OR on cooldown?
    │       └─ send set_auto_target { target_id, skill_id }
    │           → Server auto-pursues, casts when in range + off CD
    │           → Unit WAITs if in range but on cooldown
    │
    └─ HUD shows: "Approaching for <Skill>..." / "Casting <Skill>!" / "Cooldown (N)"
```

### 8.3 WASD Movement Flow

```
Player holds W+D (northeast)
    │
    ├─ useWASDMovement: resolveDirection() → [1, -1]
    │
    ├─ syncMove(): validate bounds + obstacles + occupancy
    │   └─ send batch_actions { actions: [{ move, target_x, target_y }] }
    │       (atomic: clears queue, queues 1 move, clears auto-target)
    │
    ├─ Tick resolves: unit moves northeast
    │
    ├─ Position change triggers useEffect:
    │   └─ Keys still held? → 30ms delay → syncMove() again
    │       → continuous walking, 1 tile per tick
    │
    └─ Player releases keys: last move stays queued, then stops
```

---

## 9. Key State Variables

### Client State (`GameStateContext`)

| Variable | Reducer | Type | Purpose |
|----------|---------|------|---------|
| `actionMode` | combatReducer | `string \| null` | Current action targeting mode |
| `selectedTargetId` | partyReducer | `string \| null` | Manually soft-selected target (left-click) |
| `autoTargetId` | partyReducer | `string \| null` | Auto-pursuit target (server-authoritative) |
| `autoSkillId` | partyReducer | `string \| null` | Skill tied to auto-pursuit |
| `partyAutoTargets` | partyReducer | `{ [unitId]: targetId }` | Party members' auto-targets |
| `partyAutoSkills` | partyReducer | `{ [unitId]: skillId }` | Party members' auto-skills |
| `activeUnitId` | partyReducer | `string \| null` | Currently controlled unit (self or party member) |
| `selectedUnitIds` | partyReducer | `string[]` | Multi-selected party member IDs |
| `currentQueue` | combatReducer | `PlayerAction[]` | Current action queue (per active unit) |

### Server State (per unit in `match_manager`)

| Variable | Type | Purpose |
|----------|------|---------|
| `auto_target_id` | `str \| None` | Auto-pursuit target |
| `auto_skill_id` | `str \| None` | Skill for auto-pursuit |
| `action_queue` | `list[PlayerAction]` | Queued actions (max 10) |
| `cooldowns` | `dict[str, int]` | Per-ability cooldown counters |
| `controlled_by` | `str \| None` | Which player controls this unit (party system) |
| `is_alive` | `bool` | Alive state |

---

## 10. File Reference

### Client — Input & Interaction

| File | Purpose |
|------|---------|
| `hooks/useCanvasInput.js` | Left-click (action modes + targeting) and right-click (smart pathfinding) handlers |
| `hooks/useWASDMovement.js` | WASD/Arrow key continuous movement |
| `hooks/useKeyboardShortcuts.js` | Ctrl+A, F1-F4, Ctrl+1-4, Escape |
| `hooks/useHighlights.js` | Computes valid tile highlights per action mode |
| `canvas/pathfinding.js` | Client-side A*, `generateSmartActions()`, `computeGroupRightClick()` |
| `components/BottomBar/BottomBar.jsx` | Action bar buttons, skill click handler (3 paths), hotkeys 1-5 |
| `components/HUD/HUD.jsx` | Target display, auto-target status, cooldowns |

### Client — State Management

| File | Purpose |
|------|---------|
| `context/GameStateContext.jsx` | Provider, hooks, initial state |
| `context/reducers/combatReducer.js` | `actionMode`, `currentQueue`, TURN_RESULT sync |
| `context/reducers/partyReducer.js` | `selectedTargetId`, `autoTargetId`, `autoSkillId`, party state |

### Server — Core Systems

| File | Purpose |
|------|---------|
| `core/auto_target.py` | `set_auto_target`, `clear_auto_target`, `generate_auto_target_action` |
| `core/combat.py` | Damage calc, range/LOS checks, adjacency |
| `core/turn_resolver.py` | 10-phase turn resolution |
| `core/match_manager.py` | Queue management (`queue_action`, `pop_next_actions`, `clear_player_queue`) |
| `services/tick_loop.py` | Tick orchestration: FOV → AI → queue pop → auto-target → resolve → broadcast |
| `services/message_handlers.py` | WS message dispatch: `handle_action`, `handle_batch_actions`, `handle_set_auto_target`, etc. |

---

## 11. Redundancies & Issues Found

Analysis of system interactions revealed several overlapping behaviors and pain points that degrade the player experience.

### 11.1 Right-Click Enemy Path Is Immediately Discarded

**Systems affected**: `useCanvasInput.js` (client), `message_handlers.py` → `handle_batch_actions` + `handle_set_auto_target` (server), `auto_target.py` → `set_auto_target` (server)

**The problem**: When a player right-clicks an enemy, the client does two things in sequence:
1. Sends `batch_actions` — a full client-side A* path (up to 10 optimized steps approaching the enemy)
2. Sends `set_auto_target` — which internally calls `clear_player_queue()`, wiping that entire path

So the queue fills → immediately empties → auto-target takes over generating one A* step per tick. The client computed an optimal holistic path that is **never used**. Auto-target recomputes from scratch every single tick.

**Real example**: Your Crusader is 7 tiles away from a goblin. You right-click the goblin. The client computes a beautiful 6-step path that routes around a pillar. That path is sent to the server, then instantly deleted. Auto-target starts fresh and computes step 1, then next tick step 2, etc. — potentially choosing a different, less optimal route because it only sees one step ahead at a time.

### 11.2 WASD Cancels Auto-Target (Nuclear Option)

**Systems affected**: `useWASDMovement.js` (client), `message_handlers.py` → `handle_batch_actions` (server)

**The problem**: WASD movement sends `batch_actions` (atomic clear + queue 1 move). Since `handle_batch_actions` calls `clear_auto_target()`, any movement key press cancels active pursuit. There is no way to make micro-adjustments during combat without losing your attack target.

**Real example**: Your Ranger is auto-attacking a skeleton (auto-target active, firing arrows each tick). You tap `A` to sidestep one tile left to get a better line-of-sight around a wall. Your auto-target is cancelled. Now you're just standing there. You have to right-click the skeleton again to resume attacking. In a real game you'd expect to dodge sideways and keep shooting.

### 11.3 Selected Target Cleared Too Aggressively

**Systems affected**: `combatReducer.js` → `SET_ACTION_MODE` case (client), `BottomBar.jsx` → `handleSkillClick` (client)

**The problem**: The `SET_ACTION_MODE` reducer clears `selectedTargetId` whenever an action mode is entered. This breaks the natural flow of: select a target → pick an ability to use on them.

**Current code in combatReducer.js:**
```js
case 'SET_ACTION_MODE':
  return { ...state, actionMode: action.payload, selectedTargetId: action.payload ? null : state.selectedTargetId };
```

**Real example**: You left-click an enemy Hexblade to see their HP in the HUD (selectedTargetId is set). You then click the Ranged Attack button to shoot them. The moment you click Ranged Attack, `SET_ACTION_MODE('ranged_attack')` fires and clears your `selectedTargetId`. Now the HUD shows "No Target" and the target-first casting path in `handleSkillClick` can't work because the target reference was just erased.

### 11.4 Vestigial Action Modes Still Computed

**Systems affected**: `useCanvasInput.js` (client), `useHighlights.js` (client)

**The problem**: The action modes `'move'`, `'attack'`, and `'interact'` still have full handling in both the click handler and the highlights computation, but no UI button sets them anymore (replaced by smart right-click in Phase 6E). This is dead code that runs every render cycle in `useMemo`.

**Real example**: `useHighlights.js` computes `moveHighlights` (all 8 adjacent tiles checked against obstacles), `attackHighlights` (all 8 adjacent tiles checked for enemies), and `interactHighlights` (all door tiles on the map). These arrays are allocated and computed every time the player moves, but are never displayed or consumed by any code path since no button sets those modes.

### 11.5 Ranged Attack Is a Workflow Outlier

**Systems affected**: `BottomBar.jsx` (client), `useCanvasInput.js` → `ranged_attack` mode branch (client), `useHighlights.js` → ranged highlight computation (client)

**The problem**: Every other combat action either works through smart right-click (melee) or the skill system (target-first or targeting mode). Ranged attack is the only basic action that requires: click a button → enter targeting mode → click an enemy → server validates LOS. It doesn't benefit from target-first casting, auto-target skill pursuit, or right-click context detection. It's essentially a skill without the skill system's benefits.

**Real example**: You have a Ranger with a ranged attack AND the skill "Precise Shot" (enemy_ranged targeting). To use Precise Shot, you can: left-click enemy → press hotkey → auto-pursues and casts. To use basic Ranged Attack, you must: click Ranged button → click enemy tile → hope LOS is valid (no client-side check). Two fundamentally different workflows for the same type of action.

---

## 12. QoL Recommendations

### QoL-A: Queue Drain Before Auto-Target Takes Over — ✅ IMPLEMENTED

**Priority**: 1 (High impact, medium effort)

**Goal**: When right-clicking an enemy, use the client's optimized A* path for the initial approach, then let auto-target take over only when the queue runs out.

**Changes made**:

| File | Change |
|------|--------|
| `auto_target.py` → `set_auto_target()` | **Removed** the `clear_player_queue()` call. Auto-target now coexists with a filled queue — the queue drains first, then auto-target generates actions. Also removed the now-unused `clear_player_queue` import. |
| `tick_loop.py` → Step 3.5 | No change needed — already only generates auto-target actions for units with empty queues (`pid not in submitted_ids`). |
| `message_handlers.py` → `handle_batch_actions()` | **Removed** the `clear_auto_target()` call. For non-attack right-clicks, the client sends an explicit `clear_auto_target` message, and `queue_action()` also clears any stale auto-target on the first append. |
| `useCanvasInput.js` → right-click handler | Updated comment to reflect that `batch_actions` no longer clears auto-target server-side. No logic changes needed. |

**Before (old behavior)**:
```
Right-click enemy 8 tiles away:
  Tick 1: auto-target computes step 1 (might not be optimal)
  Tick 2: auto-target computes step 2
  ...
  Tick 7: auto-target computes step 7, now adjacent
  Tick 8: auto-target generates ATTACK
```

**After (new behavior)**:
```
Right-click enemy 8 tiles away:
  Tick 1: queue pops move step 1 (client A* optimal path)
  Tick 2: queue pops move step 2
  ...
  Tick 6: queue pops move step 6 (path complete, now adjacent)
  Tick 7: queue empty → auto-target generates ATTACK
  Tick 8+: auto-target continues pursuit if enemy moves away
```

---

### QoL-B: WASD Doesn't Cancel Auto-Target

**Priority**: 2 (High impact, small effort)

**Goal**: Tapping WASD for micro-positioning shouldn't cancel active pursuit. After the WASD move resolves and keys are released, auto-target resumes.

**What changes**:

| File | Change |
|------|--------|
| `useWASDMovement.js` → `syncMove()` | Switch from `batch_actions` to a single `action` message (type: `queue_action` or a new `wasd_move` message type) that does NOT clear auto-target. |
| `message_handlers.py` | Either modify `handle_action` to not clear auto-target for move-type actions, OR add a new `handle_wasd_move` handler that queues a single move without touching auto-target. |
| `match_manager.py` → `queue_action()` | Currently clears auto-target on any manual action. Add a `preserve_auto_target=True` parameter or check `action_type == 'move'` to skip clearing. |

**Before (current)**:
```
Auto-attacking a goblin (auto-target active)
  → Press A to sidestep left
  → batch_actions sent → auto-target CLEARED
  → You stop attacking. Must right-click goblin again.
```

**After (proposed)**:
```
Auto-attacking a goblin (auto-target active)
  → Press A to sidestep left
  → wasd_move sent → move queued, auto-target PRESERVED
  → Move resolves, keys released → auto-target resumes
  → You keep attacking from new position. Seamless.
```

---

### QoL-C: Don't Clear Selected Target on Action Mode Entry

**Priority**: 3 (Medium impact, small effort)

**Goal**: The player's soft-selected target should persist when entering an action mode. It's the player's declared intent — "I'm looking at this enemy."

**What changes**:

| File | Change |
|------|--------|
| `combatReducer.js` → `SET_ACTION_MODE` case | Remove the `selectedTargetId` clearing. Change from: `selectedTargetId: action.payload ? null : state.selectedTargetId` to just keeping `state.selectedTargetId` as-is. |

That's it — one line change.

**Before (current)**:
```
Left-click enemy Hexblade → HUD shows "Hexblade, HP: 45/60"
  → Click Ranged Attack button
  → selectedTargetId cleared → HUD shows "No Target"
  → Must re-click the enemy or click their tile blindly
```

**After (proposed)**:
```
Left-click enemy Hexblade → HUD shows "Hexblade, HP: 45/60"
  → Click Ranged Attack button
  → selectedTargetId KEPT → HUD still shows "Hexblade, HP: 45/60"
  → Click the Hexblade's tile → ranged attack fires
  → Could even auto-target the selectedTargetId if using target-first path
```

---

### QoL-D: Tab-Targeting (Cycle Visible Enemies) — ✅ IMPLEMENTED

**Priority**: 4 (High impact, medium effort)

**Goal**: Press Tab to cycle `selectedTargetId` through visible enemies, nearest-first. Pairs with existing target-first skill casting for a fast combat flow.

**Changes made**:

| File | Change |
|------|--------|
| `useKeyboardShortcuts.js` | Added new `useEffect` for Tab/Shift+Tab keydown handler. Gathers all visible enemies from `players` (filtered by FOV `visibleTiles` + `team !== myTeam` + `is_alive`), sorts by Euclidean distance to active unit (nearest-first, with stable id-based tiebreaker), cycles through them updating `selectedTargetId` via `SELECT_TARGET` dispatch. Shift+Tab cycles in reverse. Uses a `useRef` to track current tab index, reset when `selectedTargetId` changes externally (e.g. left-click or Escape). |
| `useKeyboardShortcuts.js` | Updated function signature to accept `visibleTiles` and `selectedTargetId` props. |
| `Arena.jsx` | Updated `useKeyboardShortcuts()` call to pass `visibleTiles` and `selectedTargetId`. |
| `partyReducer.js` | No change needed — `SELECT_TARGET` already exists. |
| `HUD.jsx` | No change needed — already displays `selectedTargetId` info. |

**Before (old behavior)**:
```
3 enemies visible on screen. You want to check their HP and pick the weakest.
  → Left-click enemy A → see HP
  → Left-click enemy B → see HP
  → Left-click enemy C → see HP
  → Left-click enemy A again (they're the weakest)
  → Press skill hotkey to attack
  (4 precise mouse clicks + 1 key press)
```

**After (new behavior)**:
```
3 enemies visible on screen.
  → Tab → selects nearest enemy A → see HP
  → Tab → cycles to enemy B → see HP
  → Tab → cycles to enemy C → see HP
  → Shift+Tab → back to enemy A (they're the weakest)
  → Press skill hotkey → auto-pursue + cast
  (4 key presses total, no mouse needed)
```

**Implementation details**:
- Tab cycles forward (nearest → farthest), Shift+Tab cycles backward
- Enemies sorted by Euclidean distance to active unit, with stable ID-based tiebreaker
- FOV-filtered: only visible enemies appear in the cycle (respects fog of war)
- Tab index resets when target is cleared externally (Escape, left-click empty)
- Works with party control (cycles enemies relative to the controlled unit)
- `e.preventDefault()` suppresses browser's default Tab focus behavior

---

### QoL-E: Smart Ranged Auto-Target on Right-Click

**Priority**: 6 (Medium impact, medium effort)

**Goal**: Right-clicking an enemy should consider the unit's class and available abilities. If the enemy is beyond melee range but within ranged/skill range, set auto-target with the best ranged option instead of always defaulting to melee pursuit.

**What changes**:

| File | Change |
|------|--------|
| `useCanvasInput.js` → right-click handler | After determining `intent === 'attack'`, check distance to target. If > 1 tile and the active unit has ranged attack off cooldown or an offensive ranged skill off cooldown, send `set_auto_target` with the appropriate `skill_id` instead of bare melee pursuit. |
| `BottomBar.jsx` or new `combatUtils.js` | Extract a helper: `getBestRangedOption(activeUnit, skills, cooldowns)` that returns the best available ranged option. |

**Before (current)**:
```
Your Ranger is 5 tiles from a goblin. You right-click the goblin.
  → Client paths to adjacent tile (4 move steps + attack)
  → Auto-target set for melee pursuit
  → Ranger walks 4 tiles to stand next to goblin, then melees
  (Ranger has a bow. Why are they meleeing?)
```

**After (proposed)**:
```
Your Ranger is 5 tiles from a goblin. You right-click the goblin.
  → Client detects: distance=5, ranged_attack available, off cooldown
  → Auto-target set with ranged preference
  → Ranger stands still and shoots (already in range)
  → If goblin moves out of range, auto-target adjusts: walk closer, then shoot
```

---

### QoL-F: Remove Vestigial Action Modes

**Priority**: 5 (Low impact, small effort — code cleanup)

**Goal**: Remove dead code for `'move'`, `'attack'`, and `'interact'` action modes that are no longer accessible via any UI button.

**What changes**:

| File | Change |
|------|--------|
| `useCanvasInput.js` | Remove the `actionMode === 'move'`, `actionMode === 'attack'`, and `actionMode === 'interact'` branches from `handleCanvasClick`. |
| `useHighlights.js` | Remove computation of `moveHighlights`, `attackHighlights`, and `interactHighlights`. Return empty arrays for backward compat or remove entirely if no downstream consumers. |
| `BottomBar.jsx` | Verify no references to these modes exist. |

**Before (current)**:
```
Every render cycle / position change:
  → useHighlights computes moveHighlights (8 adjacent tiles checked)
  → useHighlights computes attackHighlights (8 adjacent tiles checked)
  → useHighlights computes interactHighlights (all doors on map checked)
  → None of these are ever consumed (no button sets these modes)
```

**After (proposed)**:
```
Every render cycle / position change:
  → useHighlights skips unused computations
  → Smaller memory footprint, less GC pressure
  → Cleaner code, fewer branches in click handler
```

---

### QoL-G: Sticky Auto-Target (Combines A + B)

**Priority**: 7 (High impact if A+B are done first — this is the polished version)

**Goal**: Auto-target should be a persistent combat stance, not a fragile state that any input cancels. Only intentional actions break pursuit.

**What clears auto-target (proposed)**:
| Action | Clears Auto-Target? |
|--------|---------------------|
| Right-click empty tile / door / chest | **Yes** — explicit "go somewhere else" |
| Right-click a DIFFERENT enemy | **Yes** — switches target (set new auto-target) |
| Escape key | **Yes** — universal cancel |
| WASD movement | **No** — micro-positioning |
| Left-click targeting (action modes) | **No** — manual action supplements, doesn't replace |
| `batch_actions` from right-click move | **Yes** — navigating away |
| `batch_actions` from WASD | **No** — see WASD rule above |
| Skill cast on same target | **No** — supplementary action |
| Skill cast on different target | **Yes** — target changed |

This creates an MMO-like feel where you "lock on" to a target and your character persistently engages until you deliberately disengage. Requires QoL-A and QoL-B as prerequisites.

---

### QoL-H: Auto-Select Nearest Target on Skill Press — ✅ IMPLEMENTED

**Priority**: 8 (High impact, small effort)

**Goal**: When the player presses a skill/ability hotkey (or clicks a skill button) with no pre-selected target, automatically find the nearest valid target instead of falling into targeting mode. This eliminates the mandatory Tab-target → skill workflow for common combat actions.

**Changes made**:

| File | Change |
|------|--------|
| `BottomBar.jsx` → `useGameState()` | Added `visibleTiles` to destructured state for FOV-filtered target search |
| `BottomBar.jsx` → `findNearestTarget()` | New `useCallback` helper that finds the nearest valid target for a given skill. For enemy skills (`enemy_adjacent`, `enemy_ranged`) → nearest visible alive enemy. For ally skills (`ally_or_self`) → nearest visible injured ally, or self if injured and no allies qualify. Uses Euclidean distance with stable ID tiebreaker, mirrors Tab-targeting sort logic. |
| `BottomBar.jsx` → `handleSkillClick()` | Inserted **Path B′** between existing Path B (target-first) and Path C (targeting mode). When no `selectedTargetId` exists, calls `findNearestTarget(skill)`. If a target is found: dispatches `SELECT_TARGET` (updates HUD), casts immediately if in-range + off-cooldown, and always sets `set_auto_target` for persistent pursuit. Falls through to targeting mode only if no valid target is found anywhere. |

**Before (old behavior)**:
```
3 enemies visible. Player has no target selected.
  → Press skill hotkey "2" (Power Shot)
  → Enters targeting mode: "🎯 Targeting: Power Shot — click an enemy"
  → Player must click an enemy tile to cast
  (2 inputs: hotkey + click)
```

**After (new behavior)**:
```
3 enemies visible. Player has no target selected.
  → Press skill hotkey "2" (Power Shot)
  → Auto-selects nearest visible enemy (Goblin Scout, 4 tiles away)
  → HUD updates: "🎯 Selected: Goblin Scout (enemy)"
  → In range? → casts immediately + sets auto-target
  → Out of range? → sets auto-target, pursues and casts when in range
  (1 input: hotkey only)
```

**Edge cases**:
- **Player already has a target** (`selectedTargetId` set) → unchanged, Path B handles it
- **No visible enemies** → falls through to targeting mode (Path C) as before
- **Ally heal with no injured allies** → falls through to targeting mode
- **Ally heal with injured self** → auto-targets self for healing
- **Skill on cooldown + nearest enemy found** → sets auto-target for approach (pursuit begins while cooling)
- **Tab override** → player can Tab to a different target first, then Path B handles the manually-selected target
- **FOV respected** → only considers enemies/allies on visible tiles (fog of war safe)

**Implementation details**:
- `findNearestTarget()` is a `useCallback` that iterates `players`, filters by team + alive + FOV, and returns the closest unit's ID
- For heal skills, full-HP allies are skipped (only injured units are auto-selected)
- `SELECT_TARGET` dispatch happens before the action/auto-target messages, so the HUD updates instantly
- Zero server-side changes — same `action` and `set_auto_target` messages as before

This creates an MMO-like feel where you "lock on" to a target and your character persistently engages until you deliberately disengage. Requires QoL-A and QoL-B as prerequisites.
