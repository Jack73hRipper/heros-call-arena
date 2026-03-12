# Combat System Overview

> **Last updated:** February 24, 2026
> **Purpose:** Full technical reference for how auto-attack, spells, abilities, movement, and the action queue interact. Use this to plan adjustments.

---

## Table of Contents

1. [Game Loop (Tick Cycle)](#1-game-loop-tick-cycle)
2. [Action Queue Model](#2-action-queue-model)
3. [Auto-Target / Auto-Attack System](#3-auto-target--auto-attack-system)
4. [Turn Resolution Pipeline](#4-turn-resolution-pipeline)
5. [Priority & Cancellation Rules](#5-priority--cancellation-rules)
6. [Key Interactions & Edge Cases](#6-key-interactions--edge-cases)
7. [Skills & Class Config Reference](#7-skills--class-config-reference)
8. [File Map](#8-file-map)
9. [UX Analysis — Skill/Ability Button Behavior](#9-ux-analysis--skillability-button-behavior)
10. [Recommendations](#10-recommendations)

---

## 1. Game Loop (Tick Cycle)

**File:** `server/app/services/tick_loop.py` — `match_tick()`

Every tick (default **1 second**, configurable via `match.config.tick_rate`), the server runs this sequence:

| Step | Description | Details |
|------|-------------|---------|
| **1** | Compute FOV | Recursive shadowcasting for all alive units |
| **2** | AI Decisions | `run_ai_decisions()` generates actions for AI-controlled units |
| **3** | Pop Queued Actions | `pop_next_actions()` — pops **one action** per human player from their FIFO queue |
| **3.5** | Auto-Target Generation | For humans/controlled units with **empty queues** and an active `auto_target_id`, generate one chase/attack/skill action |
| **4** | Resolve Turn | `resolve_turn()` — the full resolution pipeline (see §4) |
| **4.5** | Track Combat Stats | Damage dealt/taken, healing, items looted, turns survived |
| **5** | Recompute FOV | Positions may have changed from movement |
| **6** | Broadcast Results | FOV-filtered payloads sent to each human player via WebSocket |
| **Post** | Wave Advancement | Check if dungeon wave is cleared, spawn next wave |
| **Post** | Match End Check | Victory/defeat/extraction/party-wipe |

**Key takeaway:** Each unit gets exactly **one action per tick**. There is no simultaneous movement + attack within a single tick.

---

## 2. Action Queue Model

**File:** `server/app/core/match_manager.py` — `queue_action()`, `pop_next_actions()`

### How It Works

- Each player has a **persistent FIFO queue** (max `MAX_QUEUE_SIZE = 10` actions).
- Each tick, `pop_next_actions()` removes the **first item** from each player's queue.
- Remaining actions stay queued for future ticks.
- If the queue is empty and no auto-target is active, the player gets an implicit `WAIT`.

### How Actions Enter the Queue

| Input | WS Message Type | Behavior |
|-------|----------------|----------|
| **Left-click** (action mode active) | `action` | Appends **one** action to the queue |
| **Right-click** (smart click) | `batch_actions` | **Clears queue first**, then fills with A* pathfinding steps |
| **Group right-click** (multi-select) | `group_batch_actions` | Per-unit batch paths for all selected units |
| **Escape key** | `clear_queue` | Clears queue AND cancels auto-target |
| **Undo (Z key)** | `remove_last` | Removes last action from queue |

### Queue + Auto-Target Interaction

```
queue_action() is called
  ├── If action is MOVE / INTERACT / LOOT → CLEARS auto_target_id (+ auto_skill_id)
  │   "Repositioning means new navigational intent"
  └── If action is SKILL / ATTACK / RANGED_ATTACK / USE_ITEM / WAIT → PRESERVES auto_target
      "Combat actions enable skill weaving — auto-attacks resume when queue drains"
```

**QoL-A rule:** `batch_actions` (right-click) does NOT clear auto-target server-side. Instead:
- Right-click **enemy** → client sends `batch_actions` + `set_auto_target` (queue drains first, then auto-target takes over)
- Right-click **empty ground** → client sends `batch_actions` + explicit `clear_auto_target`

This means the batch path plays out first, and auto-target seamlessly continues pursuit when the queue empties.

---

## 3. Auto-Target / Auto-Attack System

**File:** `server/app/core/auto_target.py` — `generate_auto_target_action()`

### When It Activates

Auto-target **only generates actions when the player's queue is empty** (tick_loop Step 3.5). If there's a queued action, auto-target is skipped for that tick.

### Setting Auto-Target

- **Right-click enemy** → Client sends `set_auto_target` with `target_id` + the class's auto-attack `skill_id`
- **Skill auto-target** (Phase 10G) → `set_auto_target` with a specific `skill_id` for skill-based pursuit (e.g. right-click with skill targeting mode)
- **Skill button press** (BottomBar) → `set_auto_target` with the class's **auto-attack** `skill_id` (not the spell), so auto-attacks resume between spell cooldowns
- **Group right-click enemy** → Each selected unit gets `set_auto_target` with its own class auto-attack skill

### Decision Logic (per tick, when queue is empty)

```
1. Validate target (alive, correct team based on skill targeting type)
   └── Invalid → clear auto-target, return None

2. If auto_skill_id is set:
   ├── Resolve effective range for the skill
   ├── In range + off cooldown → Cast SKILL action
   ├── In range + on cooldown  → **Fall back to class auto-attack**
   │   ├── Auto-attack in range → Cast auto-attack SKILL
   │   ├── Auto-attack NOT in range → MOVE toward target
   │   └── No auto-attack found → WAIT (hold position)
   ├── Not in range            → MOVE one step toward target (A*)
   └── In range but no LOS     → MOVE to reposition

3. If auto_skill_id is NOT set (fallback):
   ├── Look up class's is_auto_attack skill from skills_config
   │   ├── Found → Use that skill's range/targeting
   │   │   ├── In range → Cast SKILL
   │   │   └── Not in range → MOVE toward target
   │   └── Not found → Legacy melee fallback
   │       ├── Adjacent → ATTACK action
   │       └── Not adjacent → MOVE toward target
   └── Unreachable → clear auto-target, return None
```

### Auto-Attack Skills (from `skills_config.json`)

| Skill ID | Type | Range | Cooldown | Classes |
|----------|------|-------|----------|---------|
| `auto_attack_melee` | `enemy_adjacent` | 1 (Chebyshev) | 0 turns | Crusader, Confessor, Inquisitor, Hexblade |
| `auto_attack_ranged` | `enemy_ranged` | Player's `ranged_range` | 0 turns | Ranger |

Both have `cooldown_turns: 0`, so they can fire every tick. Both route through the `SKILL` action type, resolving at **Phase 1.9** (before legacy ranged/melee).

### Clearing Auto-Target

| Trigger | Mechanism |
|---------|-----------|
| `queue_action()` with MOVE / INTERACT / LOOT | Automatic — server clears `auto_target_id` and `auto_skill_id` |
| `queue_action()` with SKILL / ATTACK / USE_ITEM | **Preserved** — combat action, auto-target survives |
| `clear_queue` message (Escape) | Handler explicitly calls `clear_auto_target()` |
| Right-click empty ground | Client sends explicit `clear_auto_target` message |
| Target dies | Server clears + notifies client (`reason: "target_died"`) |
| Target unreachable (no A* path) | Server clears + notifies client (`reason: "unreachable"`) |
| Target switches teams / becomes invalid | Server clears during validation |

---

## 4. Turn Resolution Pipeline

**File:** `server/app/core/turn_resolver.py` — `resolve_turn()`

All actions collected for a tick are **sorted by type** and resolved in strict phase order. Within each phase, actions resolve simultaneously (no ordering between players).

### Phase Order

| Phase | Name | Action Type | Key Rules |
|-------|------|-------------|-----------|
| **0** | Items | `USE_ITEM` | Potions heal, portal scrolls extract party |
| **0.5** | Cooldowns | (automatic) | All alive units' cooldowns decrement by 1 |
| **0.75** | Buffs | (automatic) | Buff durations tick down, DoT deals damage, HoT heals, expired buffs removed. **DoT can kill.** |
| **1** | Movement | `MOVE` | Batch collision resolution (`resolve_movement_batch`). Pre-move snapshot saved for melee tracking. |
| **1.5** | Doors | `INTERACT` | Open/close doors (Chebyshev adjacent required) |
| **1.75** | Loot | `LOOT` | Chest interaction + ground item pickup |
| **1.9** | Skills | `SKILL` | **All skill types**: heals, damage, buffs, teleport, AND auto-attack skills. Validates cooldown + class. **Can kill.** |
| **2** | Ranged Attacks | `RANGED_ATTACK` | Legacy ranged — LOS + cooldown validation. Per-class `ranged_range`. **Can kill.** |
| **3** | Melee Attacks | `ATTACK` | Legacy melee — adjacency check with pre-move occupant tracking. **Can kill.** |
| **3.5** | Death Loot | (automatic) | Dead enemies drop items on ground |
| **3.75** | Kill Tracking | (automatic) | Kill counters + hero permadeath |
| **4** | Victory | (automatic) | Team victory / FFA last man / dungeon extract / party wipe |

### Important Phase Ordering Implications

1. **Cooldowns tick (0.5) BEFORE skills resolve (1.9)** — A skill that just came off cooldown CAN be used that same tick.
2. **Movement (1) resolves BEFORE all combat (1.9, 2, 3)** — A player who moved this tick attacks from their NEW position.
3. **Skills (1.9) resolve BEFORE legacy ranged (2) and melee (3)** — Auto-attack skills (routed as SKILL) hit earlier than manually queued ATTACK/RANGED_ATTACK actions.
4. **DoT (0.75) can kill BEFORE the unit gets to act** — A unit at 1 HP with a DoT will die during buff ticking and won't execute their queued action.
5. **Melee uses pre-move tracking** — If a target moved this turn, melee checks both their new position AND their pre-move position for adjacency (prevents "dodge by moving").

---

## 5. Priority & Cancellation Rules

### Action Priority (per tick, per unit)

```
Priority 1: Queued action (popped from FIFO queue)
    │         ↳ Always takes precedence
    │
Priority 2: Auto-target generated action (queue is empty)
    │         ↳ Only when no queued action exists
    │
Priority 3: Implicit WAIT (human players only)
              ↳ If no queue AND no auto-target
```

### What Cancels What

| Player Action | Effect on Queue | Effect on Auto-Target |
|--------------|-----------------|----------------------|
| **Left-click MOVE** | Appends to queue | **Cleared** (repositioning intent) |
| **Left-click SKILL** | Appends to queue | **Preserved** (skill weaving) |
| **Left-click ATTACK** | Appends to queue | **Preserved** (same combat intent) |
| **Left-click USE_ITEM** | Appends to queue | **Preserved** (potion mid-fight) |
| **Left-click INTERACT** | Appends to queue | **Cleared** (door/object intent) |
| **Left-click LOOT** | Appends to queue | **Cleared** (looting intent) |
| **Right-click enemy** | Queue replaced (batch) | **Set** to new target + auto-attack skill |
| **Right-click ground/loot/door** | Queue replaced (batch) | **Cleared** (explicit `clear_auto_target`) |
| **Right-click to queue truncate** | Queue truncated | No change |
| **Escape key** | Queue cleared | **Cleared** |
| **Undo (Z)** | Last action removed | No change |
| **Skill button click** (enters action mode) | No immediate change | No change |

### Cross-System Cancellation

- **Auto-target does NOT cancel queued actions** — it only activates when the queue is empty
- **Repositioning actions (MOVE, INTERACT, LOOT) cancel auto-target** — signals navigational intent
- **Combat actions (SKILL, ATTACK, RANGED_ATTACK, USE_ITEM) preserve auto-target** — enables skill weaving; auto-attacks resume when queue drains
- **Nothing runs simultaneously** — strictly one action per unit per tick

---

## 6. Key Interactions & Edge Cases

### Movement + Attack Sequence

A right-click on a distant enemy generates a batch like:
```
Queue: [MOVE, MOVE, MOVE, MOVE, ATTACK]
                                    ↑ generated by client-side A* pathfinding
```
- Ticks 1-4: One MOVE per tick
- Tick 5: ATTACK (or SKILL, depending on path generation)
- Tick 6+: Queue empty → auto-target takes over → generates ongoing MOVE/SKILL

### Spell Casting While Moving

Not possible within a single tick. You can **queue** movement followed by a skill:
```
Queue: [MOVE, MOVE, SKILL(heal)]
```
Each executes on its own tick. There is no cast-while-moving.

### Skill Weaving (Balance-Pass)

Casting a skill **no longer breaks** auto-target pursuit. The flow:
```
Right-click enemy → set_auto_target (auto_attack_melee)
  Tick 1: Queue empty → auto_attack_melee
  Tick 2: Player presses Double Strike → SKILL(double_strike) queued
          auto_target preserved (SKILL is a combat action)
          auto_skill_id stays as auto_attack_melee (BottomBar sends
          set_auto_target with the class auto-attack skill, not the spell)
  Tick 3: Queue pops Double Strike → resolves at Phase 1.9
  Tick 4: Queue empty, auto_target still set → auto_attack_melee resumes
  Tick 5: auto_attack_melee
  ...
```

**Cooldown fallback:** If `auto_skill_id` is a non-auto-attack spell currently on
cooldown, the server **falls back to the class's auto-attack skill** (via
`_find_class_auto_attack()`) instead of WAITing. This ensures continuous combat
between spell cooldowns. Full flow:
```
set_auto_target(target, skill_id="double_strike")
  Tick 1: In range + off cooldown → cast double_strike
  Tick 2: In range + on cooldown  → fall back → auto_attack_melee
  Tick 3: In range + on cooldown  → fall back → auto_attack_melee
  Tick 4: In range + off cooldown → cast double_strike again
  ...
```

Only **repositioning actions** (MOVE, INTERACT, LOOT) clear auto-target.
Combat actions (SKILL, ATTACK, RANGED_ATTACK, USE_ITEM) preserve it, so
auto-attacks fill every tick the player isn't actively casting.

This dramatically increases auto-attack uptime and enables players to weave
skills between auto-attacks without losing pursuit.

### Auto-Attack Skill vs Legacy Attack/Ranged

The auto-target system generates `SKILL` actions (e.g. `auto_attack_melee`, `auto_attack_ranged`), not legacy `ATTACK`/`RANGED_ATTACK`. This means:

- Auto-attack resolves at **Phase 1.9** (Skills)
- Legacy melee resolves at **Phase 3**
- Legacy ranged resolves at **Phase 2**
- **Auto-attacks hit earlier** in the resolution pipeline than manual attack actions

The client's right-click `generateSmartActions()` may generate legacy `ATTACK` as the final step in a batch path. Once that legacy action executes and the queue empties, auto-target kicks in with `SKILL`-based auto-attacks.

### Ranged Auto-Attack (Ranger)

When a Ranger right-clicks an enemy:
1. Client's A* path attempts to get within `autoAttackRange` (not adjacent)
2. `set_auto_target` is sent with `skill_id: "auto_attack_ranged"`
3. Auto-target generates: approach → when in `ranged_range` with LOS → `SKILL(auto_attack_ranged)`

### Ward Reflect

Ward reflect triggers on **both melee (Phase 3) and ranged (Phase 2) attacks**, reflecting damage back to the attacker. It also triggers on skill-based attacks (Phase 1.9) via `resolve_skill_action`.

### Death During Resolution

A unit killed in an earlier phase (e.g., DoT at 0.75, or skill at 1.9) will have `is_alive = False`. Later phases skip dead units — their queued melee/ranged actions won't execute.

### Group Movement + Auto-Target

When multiple units are selected and group right-click an enemy:
- Each unit gets its own A* batch path via `group_batch_actions`
- Each unit gets `set_auto_target` with its own class's auto-attack skill
- Units independently drain their queues and then independently pursue via auto-target

### Client-Side Auto-Target State Sync

**File:** `client/src/context/reducers/combatReducer.js` — `TURN_RESULT` handler

The server includes `auto_targets` in the `turn_result` payload **only when at least one
unit has an active auto-target**. The client's `TURN_RESULT` reducer handles this:

- **`auto_targets` present in payload** → sync client state from server values
- **`auto_targets` absent** → **preserve existing client state** (no-op spread `{}`)

Previously the absent case wiped `autoTargetId` to `null`, which would break auto-attack
persistence after spell casts when the server happened to send a payload without the field.
The current behavior preserves client state until the server explicitly sends updates.

---

## 7. Skills & Class Config Reference

### All Skills (`configs/skills_config.json`)

| Skill | Targeting | Range | Cooldown | Effect | Classes |
|-------|-----------|-------|----------|--------|---------|
| `auto_attack_melee` | `enemy_adjacent` | 1 | 0 | 1.15x melee damage | Crusader, Confessor, Inquisitor, Hexblade |
| `auto_attack_ranged` | `enemy_ranged` | class range | 0 | 1.15x ranged damage | Ranger |
| `heal` | `ally_or_self` | 3 | 4 | +30 HP | Confessor, Acolyte |
| `double_strike` | `enemy_adjacent` | 1 | 3 | 2 hits @ 0.6x melee | Hexblade, Werewolf, Ghoul, Demon Lord |
| `power_shot` | `enemy_ranged` | class range | 7 | 1.8x ranged damage | Inquisitor, Ranger, Medusa |
| `war_cry` | `self` | 0 | 5 | 2.0x melee buff (2 turns) | Werewolf, Demon Lord, Demon Knight, Imp Lord |
| `shadow_step` | `empty_tile` | 3 | 4 | Teleport (requires LOS) | Hexblade, Inquisitor, Wraith, Horror, Shade |
| `wither` | `enemy_ranged` | 4 | 6 | 8 dmg/turn DoT (4 turns, refreshable) | Hexblade, Wraith, Reaper, Necromancer, Undead Caster, Horror |
| `ward` | `self` | 0 | 6 | 3 charges, 8 reflect damage | Hexblade, Construct, Construct Guardian |
| `divine_sense` | `self` | 0 | 7 | Reveal Undead/Demons (12 tiles, 4 turns) | Inquisitor |
| `venom_gaze` | `enemy_ranged` | 4 | 5 | 5 dmg/turn DoT (3 turns) | Medusa |
| `soul_reap` | `enemy_ranged` | 4 | 4 | 2.0x ranged damage | Reaper, Necromancer |
| `rebuke` | `enemy_ranged` | 6 | 7 | 24 holy dmg (36 vs Undead/Demon) | Inquisitor |
| `shield_of_faith` | `ally_or_self` | 3 | 5 | +5 armor (3 turns) | Confessor, Acolyte |
| `exorcism` | `enemy_ranged` | 5 | 4 | 20 holy dmg (40 vs Undead/Demon) | Confessor |
| `prayer` | `ally_or_self` | 4 | 6 | 8 HP/turn HoT (4 turns) | Confessor |
| `taunt` | `self` | 2 | 5 | Force nearby enemies to target you (2 turns) | Crusader |
| `shield_bash` | `enemy_adjacent` | 1 | 4 | 0.7x melee + 1-turn stun | Crusader, Undead Knight |
| `holy_ground` | `self` | 1 | 5 | AoE heal 15 HP (1-tile radius) | Crusader |
| `bulwark` | `self` | 0 | 5 | +8 armor (4 turns) | Crusader, Undead Knight, Construct Guardian |
| `volley` | `ground_aoe` | 5 | 7 | 0.5x ranged AoE (2-tile radius) | Ranger |
| `evasion` | `self` | 0 | 6 | Dodge next 2 attacks (4 turns) | Ranger, Skeleton |
| `crippling_shot` | `enemy_ranged` | class range | 5 | 0.8x ranged + 2-turn slow | Ranger |

### Class Skill Assignments

| Class | Skills |
|-------|--------|
| **Crusader** | `auto_attack_melee`, `taunt`, `shield_bash`, `holy_ground`, `bulwark` |
| **Confessor** | `auto_attack_melee`, `heal`, `shield_of_faith`, `exorcism`, `prayer` |
| **Inquisitor** | `auto_attack_melee`, `power_shot`, `shadow_step`, `divine_sense`, `rebuke` |
| **Ranger** | `auto_attack_ranged`, `power_shot`, `volley`, `evasion`, `crippling_shot` |
| **Hexblade** | `auto_attack_melee`, `double_strike`, `shadow_step`, `wither`, `ward` |
| **Wraith** (enemy) | `wither`, `shadow_step` |
| **Medusa** (enemy) | `venom_gaze`, `power_shot` |
| **Acolyte** (enemy) | `heal`, `shield_of_faith` |
| **Werewolf** (enemy) | `war_cry`, `double_strike` |
| **Reaper** (enemy) | `wither`, `soul_reap` |
| **Construct** (enemy) | `ward` |
| **Necromancer** (enemy) | `wither`, `soul_reap` |
| **Demon Lord** (enemy) | `war_cry`, `double_strike` |
| **Construct Guardian** (enemy) | `ward`, `bulwark` |
| **Undead Knight** (enemy) | `shield_bash`, `bulwark` |
| **Demon Knight** (enemy) | `war_cry` |
| **Imp Lord** (enemy) | `war_cry` |
| **Horror** (enemy) | `shadow_step`, `wither` |
| **Ghoul** (enemy) | `double_strike` |
| **Skeleton** (enemy) | `evasion` |
| **Undead Caster** (enemy) | `wither` |
| **Shade** (enemy) | `shadow_step` |

### Targeting Types

| Type | Meaning | Range Check |
|------|---------|-------------|
| `enemy_adjacent` | Must be adjacent to enemy | Chebyshev distance ≤ 1 |
| `enemy_ranged` | Ranged attack on enemy | Euclidean distance ≤ range |
| `ally_or_self` | Heal/buff self or ally | Chebyshev distance ≤ range |
| `self` | Self-only (buffs) | No range check |
| `empty_tile` | Teleport to empty tile | Euclidean distance ≤ range |
| `ground_aoe` | AoE on target tile | Euclidean distance ≤ range |

---

## 8. File Map

### Server — Combat Core

| File | Responsibility |
|------|---------------|
| `server/app/services/tick_loop.py` | Game loop — FOV, AI, queue pop, resolve, broadcast |
| `server/app/core/turn_resolver.py` | Turn resolution pipeline — all 10 phases |
| `server/app/core/combat.py` | Damage calculation (melee + ranged), armor, death, adjacency, LOS |
| `server/app/core/auto_target.py` | Persistent auto-target pursuit + skill auto-targeting |
| `server/app/core/match_manager.py` | Match lifecycle, action queue (FIFO), player state, FOV cache |
| `server/app/core/skills.py` | Skill definitions, `can_use_skill`, `resolve_skill_action`, buff logic |
| `server/app/services/message_handlers.py` | WebSocket message dispatch — `handle_action`, `handle_batch_actions`, `handle_set_auto_target`, etc. |
| `server/configs/skills_config.json` | All skill definitions + class-to-skill mappings |
| `server/configs/combat_config.json` | Base health, damage, armor reduction tuning |
| `server/configs/classes_config.json` | Per-class stats (HP, damage, range, vision, speed) |

### Client — Input & State

| File | Responsibility |
|------|---------------|
| `client/src/hooks/useCanvasInput.js` | Click/right-click handlers — builds actions, sends to server |
| `client/src/canvas/pathfinding.js` | Client-side A* for smart right-click path generation |
| `client/src/context/reducers/combatReducer.js` | Combat state reducer (queue, auto-target, turn results) |
| `client/src/context/reducers/partyReducer.js` | Party selection, stances, auto-target state |
| `client/src/hooks/useHighlights.js` | Valid tile highlights for each action mode |
| `client/src/hooks/useKeyboardShortcuts.js` | Hotkeys (Escape = clear queue, F-keys, Ctrl+A, etc.) |

---

## Flow Diagram

```
  Player Input (click/right-click/hotkey)
         │
         ▼
  ┌─────────────────┐
  │  WebSocket Msg   │  action / batch_actions / set_auto_target / clear_auto_target
  └────────┬────────┘
           ▼
  ┌─────────────────┐
  │  Message Handler │  Validates, builds PlayerAction, calls queue_action()
  └────────┬────────┘
           ▼
  ┌─────────────────┐
  │  Action Queue    │  FIFO per player (max 10). queue_action() clears auto-target.
  │  (match_manager) │
  └────────┬────────┘
           │
     ══════╪═════════════  TICK BOUNDARY  ═══════════════
           │
           ▼
  ┌─────────────────┐
  │  match_tick()    │  Step 3: pop_next_actions() — one per player
  │  (tick_loop)     │  Step 3.5: auto-target fills in if queue was empty
  └────────┬────────┘
           ▼
  ┌─────────────────────────────────────────────────────┐
  │              resolve_turn() Pipeline                 │
  │                                                      │
  │  Phase 0    ─  Items (potions, scrolls)              │
  │  Phase 0.5  ─  Cooldown tick (all units)             │
  │  Phase 0.75 ─  Buff/DoT/HoT tick (can kill)         │
  │  Phase 1    ─  Movement (batch collision)            │
  │  Phase 1.5  ─  Door interactions                     │
  │  Phase 1.75 ─  Loot pickup                           │
  │  Phase 1.9  ─  SKILLS (all types, incl auto-attack)  │
  │  Phase 2    ─  Legacy ranged attacks                  │
  │  Phase 3    ─  Legacy melee attacks                   │
  │  Phase 3.5  ─  Death loot drops                       │
  │  Phase 3.75 ─  Kill tracking + permadeath             │
  │  Phase 4    ─  Victory check                          │
  └────────┬────────────────────────────────────────────┘
           ▼
  ┌─────────────────┐
  │  Broadcast       │  FOV-filtered turn_result + queue_updated to each player
  └─────────────────┘
```

---

## 9. UX Analysis — Skill/Ability Button Behavior

> **Context:** In-game, skills and abilities feel unclear. The purple glow on buttons is confusing, failed casts are silent, and the effect of pressing buttons multiple times is unintuitive. This section documents exactly what's happening behind the scenes.

### 9.1 The Purple Glow = "Targeting Mode Active"

**File:** `client/src/components/BottomBar/BottomBar.jsx` — `handleSkillClick()`
**Style:** `client/src/styles/main.css` — `.btn-skill.active`

When you click a skill button, the button gets the CSS class `active`, which styles it with:
- Purple background: `rgba(160, 80, 240, 0.2)`
- Purple border: `#a050f0`
- Purple glow: `box-shadow: 0 0 8px rgba(160, 80, 240, 0.4)`

**What it actually means:** The skill has entered **targeting mode** — the system is waiting for you to **left-click a valid tile/target** on the canvas. The skill has NOT been cast. The purple glow is a state indicator that the game is waiting for a second click.

**The problem:** There is no visual distinction between "targeting mode is active" and "I cast something." There's no text prompt on the canvas, no cursor change, and no toast/notification saying "pick a target." If you don't understand the two-step flow, the purple glow looks like a confirmation.

### 9.2 Why Spells Sometimes Don't Cast (Silent Failures)

Multiple code paths can silently eat a skill click with zero feedback:

| Failure Scenario | What Actually Happens | Feedback to Player |
|-----------------|----------------------|-------------------|
| **No target selected, skill is not `self`** | Enters targeting mode (purple) — waits for click. Skill is NOT queued. | Purple glow only. No "pick a target" prompt. |
| **On cooldown, no selected target** | `handleSkillClick()` hits `if (cooldown > 0) return;` — does nothing. | Button appears dimmed (50% opacity), but no error message or toast. |
| **Click invalid tile while in targeting mode** | `useCanvasInput.js` checks `skillHighlights.some(...)` — if tile isn't valid, the click is ignored entirely. | Nothing. No "invalid target" feedback. |
| **Target out of range during resolution** | Server resolves the SKILL action, finds it fails validation in `_resolve_skills()`. Returns `ActionResult(success=False, message="cannot use skill — {reason}")`. | Shows as a `'miss'` type entry in combat log. Easy to miss in scroll. |
| **Target died before skill resolves** | Server skips dead casters in `_resolve_skills()`. The action is consumed silently. | No log entry at all for the skipped action. |
| **Queue is full** | `handleSkillClick()` hits `if (isDead \|\| queueFull) return;` — does nothing. | Button is disabled, but no explicit "queue full" toast. |

**Key pain point:** The combat log is the **only** error channel for server-side skill failures, and it's presented as a small `'miss'` text that scrolls away quickly. Client-side failures produce zero feedback.

### 9.3 Pressing the Same Skill Button Multiple Times

The behavior depends entirely on whether you have a **selected target** (left-clicked a unit) or not.

#### Path A: No Selected Target

```
Press 1 (Heal):  actionMode was null → SET_ACTION_MODE('skill_heal')
                  Button glows purple. Targeting mode ON.

Press 1 (Heal):  actionMode === 'skill_heal' → SET_ACTION_MODE(null)
                  Button un-glows. Targeting mode OFF.

Press 1 (Heal):  actionMode was null → SET_ACTION_MODE('skill_heal')
                  Purple again. Targeting mode ON.
```

**It's a toggle.** Same button twice = cancel. This is unintuitive because it looks like you're trying to cast twice, but you're actually canceling.

#### Path B: With a Selected Target (left-clicked a unit first)

```
Press 1 (Heal):  selectedTargetId exists, target is valid ally
                  → In range + off cooldown? QUEUES the SKILL action immediately.
                  → Also sends set_auto_target with the class's **auto-attack**
                    skill_id (not the spell), so auto-attacks resume between
                    spell cooldowns.
                  Does NOT enter targeting mode. Returns early.

Press 1 (Heal):  selectedTargetId still set (wasn't cleared)
                  → Same logic runs again. QUEUES ANOTHER SKILL action.
                  Two skill actions now in queue.
```

**With a target selected, each press queues a separate action.** No guards against double-queuing the same skill. This can waste queue slots (especially since a 4-turn-cooldown skill will fail on the second execution anyway).

**Auto-target is preserved with auto-attack skill:** The `set_auto_target` message uses
the class's `is_auto_attack` skill (`auto_attack_melee` or `auto_attack_ranged`), NOT the
spell being cast. This ensures the auto-target system generates auto-attacks between spell
cooldowns instead of WAITing.

### 9.4 Pressing Different Skill Buttons

#### Path A: No Selected Target (targeting mode)

```
Press 1 (Heal):   actionMode = 'skill_heal'     → Heal targeting mode (purple on Heal)
Press 2 (Double):  actionMode ≠ 'skill_double_strike'
                   → SET_ACTION_MODE('skill_double_strike')
                   → Heal targeting mode OFF, Double Strike mode ON.
                   Purple glow moves from button 1 to button 2.
```

**Last one wins.** Only one targeting mode active at a time. Switching is instant with no acknowledgment that the previous mode was canceled.

#### Path B: With a Selected Target

```
Press 1 (Heal):    Queues Heal + sets auto-target with auto-attack skill.
Press 2 (Double):  Queues Double Strike + sets auto-target with auto-attack skill.
                   Both are now in the queue. Auto-target stays on same enemy
                   with the class auto-attack skill (not overwritten to a spell).
```

**Both queue independently.** The `set_auto_target` messages both use the class's auto-attack
skill, so pressing different spells doesn't change the pursuit behavior.

### 9.5 Summary of Current Problems

| Problem | Root Cause | Severity |
|---------|-----------|----------|
| Purple glow meaning unclear | No "pick a target" prompt, no distinction from "cast confirmed" | High |
| Skills silently fail to cast | Multiple `return` paths with no UI feedback | High |
| Same-skill toggle is unintuitive | Press twice = cancel, not "cast twice" | Medium |
| Double-queue with selected target | No guards against queuing same skill repeatedly | Low |
| No cast confirmation | Skill queues silently — no flash, animation, or sound cue | Medium |
| Combat log is only error channel | Failed casts buried as 'miss' entries in scrolling log | Medium |

---

## 10. Recommendations

### 10.1 Add Explicit "Targeting Mode" Visual Indicator

**Problem:** The purple button glow is the only indicator that a skill is waiting for a target click.

**Recommendation:**
- When entering targeting mode, display a **brief floating text** above the action bar or on the canvas: *"Select a target for [Heal]"* or *"Click an enemy in range for [Double Strike]"*
- Change the **cursor style** to a crosshair or skill-specific cursor when in targeting mode, so the player knows the next click is meaningful
- Add a subtle **pulsing animation** to the skill highlights on the map tiles to draw the eye toward valid targets
- The hint text row already exists in BottomBar (`bottom-bar-hint`) and generates targeting hints via `getTargetingHint()` — but it's small and easy to miss. Consider making it more prominent (larger font, contrasting color, or move it closer to the canvas)

### 10.2 Add Feedback for Failed / Blocked Skill Casts

**Problem:** Clicking a skill when it can't fire (cooldown, no target, invalid tile) produces no feedback.

**Recommendation:**
- **Client-side blocks** (cooldown, queue full, no valid target): Show a brief **toast notification** or inline flash on the button: *"On cooldown (2 turns)"*, *"Queue full"*, *"No valid target"*
- **Server-side failures**: In addition to the combat log `'miss'` entry, dispatch a **combat floater** at the caster's position: *"Blocked!"* or *"Out of range"* in a distinct color (gray or orange)
- Consider a brief **button shake animation** when a skill click is rejected, giving immediate tactile feedback that "this didn't work"
- The `bottom-bar-hint` row could be repurposed to show error flash messages that fade after 1-2 seconds

### 10.3 Replace Toggle Behavior with Consistent "Cast or Enter Targeting"

**Problem:** Pressing the same skill button twice cancels targeting mode, which reads as "I tried to cast twice."

**Recommendation:**
- **Remove the toggle-off on same-button press.** Instead, pressing the same skill while in targeting mode should be a no-op (mode stays active). Let the player cancel targeting via **Escape** or **right-click** (which already cancel modes).
- Alternatively: if the player presses the same skill button again while in targeting mode, treat it as "cast on self" for `ally_or_self` skills, or "confirm auto-attack pursuit" for offensive skills with a selected target. This makes the second press meaningful instead of a cancel.
- **For different skill buttons:** Keep the current "last one wins" replacements — this feels natural and is standard in action-RPGs.

### 10.4 Add Cast Confirmation Feedback

**Problem:** When a skill successfully queues, there's no visual or audio acknowledgment.

**Recommendation:**
- **Brief green flash** on the skill button when it successfully queues (CSS animation, ~300ms)
- **Queue number badge** on the button: if two Heals are queued, show a small "2" on the Heal button so the player knows multiple casts are pending
- **Canvas feedback**: a brief targeting-line or projectile preview at the moment of queuing, so the player sees where the skill will go
- Consider showing the queued skill as an **icon in the queue display** (currently just "3 actions" text), so the player can see *what* is queued

### 10.5 Guard Against Redundant Skill Queuing

**Problem:** With a selected target, mashing a skill button queues it repeatedly. The second+ copies will fail server-side (cooldown) and waste queue slots.

**Recommendation:**
- After queuing a skill via the "selected target" fast-path, **set a brief lockout** (e.g., 200ms debounce or check if the same `skill_id` is already the last item in the queue)
- Or: check the current queue for an identical pending skill action before appending. If the same skill targeting the same unit is already queued, skip or show *"Already queued"*
- For auto-target skills: the server already handles this correctly (last `set_auto_target` wins). No code change needed — just don't additionally queue a SKILL action.

### 10.6 Unify the Skill Action Path (Longer-Term)

**Problem:** There are currently two parallel paths that generate combat actions: legacy `ATTACK`/`RANGED_ATTACK` types (from client A* path generation) and `SKILL` types (from auto-target). They resolve at different phases (1.9 vs 2/3), creating subtle timing differences.

**Recommendation (longer-term):**
- Migrate the client's `generateSmartActions()` to generate `SKILL(auto_attack_melee)` or `SKILL(auto_attack_ranged)` instead of legacy `ATTACK`/`RANGED_ATTACK` for the final step in A* paths
- This eliminates the phase-ordering discrepancy and makes all combat flow through the same pipeline
- Not urgent, but would simplify the codebase and remove an edge case where the same player's attacks resolve at different speeds depending on how they were initiated
