# Phase 6: Skills / Spells System & Dungeon UI Overhaul — Design Document

## Overview

**Goal:** Introduce an active skill/spell system with class-specific abilities, a dedicated skill bar UI, keyboard shortcut support, and a reorganized dungeon GUI that fits within a single viewport.

**Timeline:** 4–5 weeks (7 sub-phases)  
**Status:** Phase 6C Complete  
**Prerequisites:** Phase 5 Feature 7 (Town Gear Management) complete — 627 tests passing

---

## Phase 5 Status (Current State)

**Completed:**
- ✅ 5 playable classes with unique stats (Crusader, Confessor, Inquisitor, Ranger, Hexblade)
- ✅ Full combat pipeline: Move → Interact → Loot → Ranged → Melee → Death → Victory
- ✅ Cooldown system (generic `dict[str, int]` on PlayerState, ticked each turn)
- ✅ Persistent action queue (up to 10 actions), batch queuing, undo/clear
- ✅ Party control system (select ally → issue commands)
- ✅ Equipment, inventory, loot drops, consumables (Health Potion, Portal Scroll)
- ✅ Hero persistence, permadeath, town hub, merchant, bank
- ✅ Placeholder `skills_config.json` exists (3 skills defined but disabled)

**Key Architecture Points:**
- `ActionType` enum: `MOVE`, `ATTACK`, `RANGED_ATTACK`, `WAIT`, `INTERACT`, `LOOT`, `USE_ITEM`
- `PlayerAction` model: `player_id`, `action_type`, `target_x`, `target_y`
- Turn resolver runs phases in order: Items → Cooldowns → Movement → Interact → Loot → Ranged → Melee → Death → Victory
- Cooldowns already generic — `player.cooldowns["ranged_attack"] = 3` pattern
- WS handler validates `action_type` against a whitelist string set
- ActionBar buttons: Move, Attack, Ranged, Wait, Interact (dungeon), Loot (dungeon), Potion (dungeon)
- Arena sidebar layout: HUD → PartyPanel → ActionBar → Inventory → CombatLog → Leave

---

## Sub-Phase Summary

| Sub-Phase | Description | Priority | Estimated Effort |
|-----------|-------------|----------|-----------------|
| **6A** | Skills config, server models, class-skill mapping | High | 2–3 days |
| **6B** | Turn resolver skill phase + combat logic | High | 2–3 days |
| **6C** | WS protocol extensions + client state | High | 1–2 days |
| **6D** | SkillBar UI component + canvas targeting | High | 2–3 days |
| **6E** | Dungeon GUI reorganization | Medium | 2–3 days |
| **6F** | Keyboard shortcuts (1–9 skills, hotkeys) | Medium-Low | 1–2 days |
| **6G** | AI skill usage (enemies/bosses use skills) | Low | 2–3 days |

---

## Sub-Phase 6A: Skills Config & Server Models

### Goal
Define the skill/spell data schema, populate initial skills, map skills to classes, and extend server models to support skill actions.

### Tasks

#### 1. Rewrite `skills_config.json`

Replace the existing placeholder with a structured skill registry. Each skill has a unique `skill_id` and defines its targeting, effects, cooldown, and class restrictions.

```json
{
  "skills": {
    "heal": {
      "skill_id": "heal",
      "name": "Heal",
      "description": "Restore HP to yourself or an adjacent ally.",
      "icon": "💚",
      "targeting": "ally_or_self",
      "range": 1,
      "cooldown_turns": 4,
      "mana_cost": 0,
      "effects": [
        { "type": "heal", "magnitude": 30 }
      ],
      "allowed_classes": ["confessor"],
      "requires_line_of_sight": false
    },
    "double_strike": {
      "skill_id": "double_strike",
      "name": "Double Strike",
      "description": "Strike an adjacent enemy twice at 60% damage each hit.",
      "icon": "⚔️⚔️",
      "targeting": "enemy_adjacent",
      "range": 1,
      "cooldown_turns": 3,
      "mana_cost": 0,
      "effects": [
        { "type": "melee_damage", "hits": 2, "damage_multiplier": 0.6 }
      ],
      "allowed_classes": ["crusader", "hexblade"],
      "requires_line_of_sight": false
    },
    "power_shot": {
      "skill_id": "power_shot",
      "name": "Power Shot",
      "description": "A devastating ranged attack at 1.8x damage. Longer cooldown than normal ranged.",
      "icon": "🎯",
      "targeting": "enemy_ranged",
      "range": 0,
      "cooldown_turns": 5,
      "mana_cost": 0,
      "effects": [
        { "type": "ranged_damage", "damage_multiplier": 1.8 }
      ],
      "allowed_classes": ["ranger", "inquisitor"],
      "requires_line_of_sight": true
    },
    "war_cry": {
      "skill_id": "war_cry",
      "name": "War Cry",
      "description": "Buff yourself — next melee attack deals 2x damage. Lasts 2 turns.",
      "icon": "📯",
      "targeting": "self",
      "range": 0,
      "cooldown_turns": 5,
      "mana_cost": 0,
      "effects": [
        { "type": "buff", "stat": "melee_damage_multiplier", "magnitude": 2.0, "duration_turns": 2 }
      ],
      "allowed_classes": ["crusader"],
      "requires_line_of_sight": false
    },
    "shadow_step": {
      "skill_id": "shadow_step",
      "name": "Shadow Step",
      "description": "Teleport to a tile within 3 range (must be unoccupied, must have LOS).",
      "icon": "👤",
      "targeting": "empty_tile",
      "range": 3,
      "cooldown_turns": 4,
      "mana_cost": 0,
      "effects": [
        { "type": "teleport" }
      ],
      "allowed_classes": ["hexblade", "inquisitor"],
      "requires_line_of_sight": true
    }
  },
  "class_skills": {
    "crusader":   ["double_strike", "war_cry"],
    "confessor":  ["heal"],
    "inquisitor": ["power_shot", "shadow_step"],
    "ranger":     ["power_shot"],
    "hexblade":   ["double_strike", "shadow_step"]
  },
  "max_skill_slots": 4
}
```

**Design notes:**
- `targeting` enum: `"self"`, `"ally_or_self"`, `"enemy_adjacent"`, `"enemy_ranged"`, `"empty_tile"`
- `range: 0` means "use the unit's own `ranged_range` stat"
- `mana_cost: 0` — mana is reserved for a future phase, but the field exists for forward-compat
- `allowed_classes` — restricts which classes can learn/use this skill
- `class_skills` — maps each class to its available skill list (ordered for default skill bar)
- Start with 5 skills across 5 classes; more can be added to config without code changes

#### 2. Extend `ActionType` enum

**File:** `server/app/models/actions.py`

```python
class ActionType(str, Enum):
    MOVE = "move"
    ATTACK = "attack"
    RANGED_ATTACK = "ranged_attack"
    WAIT = "wait"
    INTERACT = "interact"
    LOOT = "loot"
    USE_ITEM = "use_item"
    SKILL = "skill"           # NEW — Phase 6A
```

#### 3. Extend `PlayerAction` model

Add an optional `skill_id` field:

```python
class PlayerAction(BaseModel):
    player_id: str
    action_type: ActionType
    target_x: int | None = None
    target_y: int | None = None
    skill_id: str | None = None    # NEW — Phase 6A: which skill to use
```

#### 4. Add `active_buffs` to `PlayerState`

**File:** `server/app/models/player.py`

```python
class PlayerState(BaseModel):
    # ... existing fields ...
    # Phase 6A: Active buffs/debuffs — list of {buff_id, stat, magnitude, turns_remaining}
    active_buffs: list[dict] = Field(default_factory=list)
```

Buffs tick down each turn alongside cooldowns. Combat functions check `active_buffs` for damage multipliers, damage reduction, etc.

#### 5. Skill loader utility

**File (new):** `server/app/core/skills.py`

Create a module that:
- Loads `skills_config.json` at startup (same pattern as `combat.py` loading `combat_config.json`)
- Provides `get_skill(skill_id) -> dict | None`
- Provides `get_class_skills(class_id) -> list[str]` — returns ordered list of skill_ids for a class
- Provides `can_use_skill(player: PlayerState, skill_id: str) -> tuple[bool, str]` — validates cooldown, class restriction, alive status

#### 6. Extend `ActionResult` model

Add optional `skill_id` to `ActionResult` so the client knows which skill resolved:

```python
class ActionResult(BaseModel):
    # ... existing fields ...
    skill_id: str | None = None     # NEW — Phase 6A
    buff_applied: dict | None = None  # NEW — {stat, magnitude, duration}
    heal_amount: int | None = None    # NEW — for heal skill results
```

#### 7. Add `TurnResult.buff_changes` field

```python
class TurnResult(BaseModel):
    # ... existing fields ...
    buff_changes: list[dict] = Field(default_factory=list)  # [{player_id, buffs: [...]}]
```

### Tests to Write
- Skill config loading — all 5 skills parse correctly
- `get_class_skills` returns correct skills for each class
- `can_use_skill` validates cooldown, class restriction, dead unit
- `ActionType.SKILL` serializes/deserializes correctly
- `PlayerAction` with `skill_id` field works
- Backward compat — all existing 627 tests still pass (SKILL enum doesn't break anything)

### Files Modified
| File | Change |
|------|--------|
| `server/configs/skills_config.json` | Rewrite with full skill definitions |
| `server/app/models/actions.py` | Add `SKILL` to ActionType, `skill_id` to PlayerAction, extend ActionResult/TurnResult |
| `server/app/models/player.py` | Add `active_buffs` field to PlayerState |
| `server/app/core/skills.py` | **New file** — skill loader + validation utilities |
| `server/app/services/websocket.py` | Add `"skill"` to action type whitelists, pass `skill_id` through to PlayerAction |
| `server/tests/test_skills.py` | **New file** — 61 tests covering config, models, validation |

### Acceptance Criteria
- [x] `skills_config.json` defines 5 skills with targeting, cooldown, effects, class restrictions
- [x] `ActionType.SKILL` exists and serializes to `"skill"`
- [x] `PlayerAction.skill_id` is optional, only used when `action_type == SKILL`
- [x] `PlayerState.active_buffs` field exists (default empty list)
- [x] Skill loader can parse config, return class skill lists, validate usage
- [x] All 627 existing tests pass unchanged (backward compat) — 752 total (691 existing + 61 new)
- [x] New tests: 61 covering skill config, models, validation, cross-referencing

### Implementation Notes (Phase 6A — completed 2026-02-14)
- Rewrote `skills_config.json` with 5 skills: Heal, Double Strike, Power Shot, War Cry, Shadow Step
- Added `SKILL = "skill"` to `ActionType` enum
- Added optional `skill_id` field to `PlayerAction` model
- Added `skill_id`, `buff_applied`, `heal_amount` fields to `ActionResult`
- Added `buff_changes` field to `TurnResult`
- Added `active_buffs: list[dict]` to `PlayerState` (default empty)
- Created `server/app/core/skills.py` with: `load_skills_config()`, `get_skill()`, `get_all_skills()`, `get_class_skills()`, `get_max_skill_slots()`, `can_use_skill()`, `clear_skills_cache()`
- Updated WS handler action whitelist to accept `"skill"` in both single-action and batch-action flows
- WS handler passes `skill_id` through to `PlayerAction` construction and queue serialization
- 61 new tests in `test_skills.py` across 9 test classes
- Full backward compat verified: 752 tests passing, 0 failures

---

## Sub-Phase 6B: Turn Resolver Skill Phase & Combat Logic

### Goal
Add a skill resolution phase to the turn resolver. Implement the actual effect logic for each skill type: heal, multi-hit melee, boosted ranged, self-buff, and teleport.

### Tasks

#### 1. Add Skill Resolution Phase to `turn_resolver.py`

Insert a new phase between Loot (Phase 1.75) and Ranged (Phase 2):

```
Resolution Order (updated):
  0.   Item-use phase (potions, scrolls)
  0.5  Tick cooldowns
  0.75 Tick active buffs (decrement turns, remove expired)    ← NEW
  1.   Movement
  1.5  Interaction (doors)
  1.75 Loot (chests + ground pickup)
  1.9  Skill resolution                                       ← NEW
  2.   Ranged attacks
  3.   Melee attacks
  3.5  Loot drops from deaths
  3.75 Kill tracking + permadeath
  4.   Victory check
```

**Why before ranged/melee:** Buff skills (War Cry) should apply before attacks resolve that same turn. Heal should apply before combat so a just-healed unit survives. Teleport should resolve before attacks so the unit has moved.

#### 2. Skill Action Separation

In `resolve_turn`, filter skill actions:

```python
skill_actions = [a for a in actions if a.action_type == ActionType.SKILL]
```

#### 3. Implement Skill Effect Handlers

Create individual effect handler functions in `server/app/core/skills.py`:

**`resolve_heal(player, target, skill_def, players, obstacles)`**
- Find target at `(target_x, target_y)` — must be self or an alive ally within range
- Apply heal: `target.hp = min(target.max_hp, target.hp + magnitude)`
- Apply cooldown: `player.cooldowns[skill_id] = cooldown_turns`
- Return `ActionResult` with `heal_amount`

**`resolve_multi_hit(player, target, skill_def, players, obstacles)`**
- Find enemy target at `(target_x, target_y)` — must be adjacent
- Calculate base melee damage, multiply by `damage_multiplier`, apply N hits
- Each hit applies damage separately (armor applies per-hit)
- Apply cooldown
- Return `ActionResult` with total damage dealt, killed status

**`resolve_ranged_skill(player, target, skill_def, players, obstacles)`**
- Find enemy target at `(target_x, target_y)` — must be in range + have LOS
- Calculate ranged damage × `damage_multiplier`
- Apply cooldown
- Return `ActionResult`

**`resolve_buff(player, skill_def)`**
- Add entry to `player.active_buffs`: `{ "buff_id": skill_id, "stat": stat, "magnitude": magnitude, "turns_remaining": duration }`
- Apply cooldown
- Return `ActionResult` with `buff_applied`

**`resolve_teleport(player, target_x, target_y, skill_def, obstacles, occupied)`**
- Validate target tile: in range, not obstacle, not occupied, has LOS
- Move player to target tile
- Apply cooldown
- Return `ActionResult` with movement fields

#### 4. Buff Application in Combat

Modify `combat.py` functions to check `active_buffs`:

```python
def calculate_damage(attacker, defender):
    # ... existing equipment bonus logic ...
    # Check for melee_damage_multiplier buff
    melee_mult = 1.0
    for buff in attacker.active_buffs:
        if buff.get("stat") == "melee_damage_multiplier":
            melee_mult *= buff["magnitude"]
    raw_damage = int((attacker.attack_damage + atk_bonuses.attack_damage) * melee_mult)
    # ... rest unchanged ...
```

Similarly for ranged damage multipliers, damage reduction buffs, etc.

#### 5. Buff Tick Phase

Add to turn resolver after cooldown tick:

```python
# --- Phase 0.75: Tick active buffs ---
for p in players.values():
    if p.is_alive and p.active_buffs:
        remaining = []
        for buff in p.active_buffs:
            buff["turns_remaining"] -= 1
            if buff["turns_remaining"] > 0:
                remaining.append(buff)
        p.active_buffs = remaining
```

#### 6. Consume Buff on Use (War Cry)

For the War Cry buff specifically, the melee damage multiplier should be consumed after the first melee attack that uses it (alternatively, it lasts the full duration). Decision: **lasts full duration** for simplicity in Phase 6. Single-use consumption can be added later as a buff property.

### Tests to Write
- **Heal skill:** Confessor heals self, heals adjacent ally, can't heal enemy, can't heal when on cooldown, heal caps at max_hp
- **Double Strike:** 2 hits applied, each reduced by armor, kill on second hit, not adjacent = fail
- **Power Shot:** 1.8x ranged damage, requires LOS, blocked by obstacles, applies its own cooldown (separate from ranged_attack cooldown)
- **War Cry:** Buff applied, next melee does 2x, buff decays after duration, buff stacking behavior
- **Shadow Step:** Teleports to valid tile, blocked by obstacle/occupied/out-of-range/no-LOS
- **Buff tick:** Buffs decrement each turn, expired buffs removed
- **Integration:** Skills resolve before ranged and melee phases
- **Backward compat:** All existing 627+ tests still pass

### Files Modified
| File | Change |
|------|--------|
| `server/app/core/turn_resolver.py` | Add skill resolution phase (1.9), buff tick phase (0.75) |
| `server/app/core/skills.py` | Add effect handler functions |
| `server/app/core/combat.py` | Check `active_buffs` in damage calculation |
| `server/tests/test_skills_combat.py` | **New file** — 75 tests covering all 5 skills, buff system, integration |

### Acceptance Criteria
- [x] All 5 starter skills resolve correctly in the turn resolver
- [x] Cooldowns apply per-skill (separate from ranged_attack cooldown)
- [x] Buffs tick down each turn and are removed when expired
- [x] Buff effects modify combat calculations (melee multiplier confirmed)
- [x] Heal restores HP, capped at max_hp
- [x] Teleport validates range, LOS, obstacle, occupied checks
- [x] Multi-hit applies armor reduction per hit
- [x] All existing tests pass (backward compat)
- [x] New tests: 75 covering all 5 skills, buff system, integration, backward compat

### Implementation Notes (Phase 6B — completed 2026-02-14)
- Added buff tick phase (0.75) to turn resolver — decrements all active_buffs each turn, removes expired
- Added skill resolution phase (1.9) between loot and ranged — dispatches to effect handlers
- Implemented 5 effect handlers in `skills.py`: `resolve_heal`, `resolve_multi_hit`, `resolve_ranged_skill`, `resolve_buff`, `resolve_teleport`
- Added `resolve_skill_action` dispatcher that routes by effect type
- Added `tick_buffs(player)` utility — returns list of expired buffs for logging
- Added `get_melee_buff_multiplier(player)` and `get_ranged_buff_multiplier(player)` helpers
- Modified `combat.py` `calculate_damage()` to apply melee buff multiplier from active_buffs
- Modified `combat.py` `calculate_ranged_damage()` to apply ranged buff multiplier from active_buffs
- Skill kills register in `deaths` list and propagate through loot drops + permadeath phases
- Buff changes tracked in `TurnResult.buff_changes` for client sync
- War Cry buff lasts full duration (not consumed on use) per design decision
- Double Strike with War Cry applies boosted base damage before per-hit multiplier
- 75 new tests in `test_skills_combat.py` across 11 test classes
- Full backward compat verified: 827 tests passing, 0 failures

---

## Sub-Phase 6C: WebSocket Protocol & Client State

### Goal
Extend the WS protocol to support skill actions and sync skill/buff state to the client. Update the GameState reducer to track skills, cooldowns, and buffs.

### Tasks

#### 1. WS Handler — Accept `skill` action type

**File:** `server/app/services/websocket.py`

Add `"skill"` to the `action_type` whitelist:

```python
if action_type not in ("move", "attack", "ranged_attack", "wait", "interact", "loot", "use_item", "skill"):
```

When `action_type == "skill"`, read `skill_id` from the message and pass it through to `PlayerAction`:

```python
action = PlayerAction(
    player_id=unit_id,
    action_type=ActionType(action_type),
    target_x=data.get("target_x"),
    target_y=data.get("target_y"),
    skill_id=data.get("skill_id"),  # NEW
)
```

#### 2. Include class skills in match_start payload

When `match_start` is broadcast, include the player's available skills:

```json
{
  "type": "match_start",
  "players": { ... },
  "class_skills": {
    "crusader": [
      { "skill_id": "double_strike", "name": "Double Strike", "icon": "⚔️⚔️", "cooldown_turns": 3, "targeting": "enemy_adjacent", "range": 1, "description": "..." },
      { "skill_id": "war_cry", "name": "War Cry", "icon": "📯", "cooldown_turns": 5, "targeting": "self", "range": 0, "description": "..." }
    ]
  }
}
```

This allows the client to build the skill bar without needing a separate REST call.

#### 3. Include cooldowns + buffs in turn_result payload

The existing `turn_result` broadcast already includes full `players` dict. Ensure each player's `cooldowns` dict and new `active_buffs` list are serialized:

```json
{
  "type": "turn_result",
  "players": {
    "player_abc": {
      "cooldowns": { "ranged_attack": 2, "heal": 3 },
      "active_buffs": [{ "buff_id": "war_cry", "stat": "melee_damage_multiplier", "magnitude": 2.0, "turns_remaining": 1 }]
    }
  }
}
```

#### 4. Update GameState initial state + reducer

**File:** `client/src/context/GameStateContext.jsx`

Add to `initialState`:
```js
classSkills: [],        // Array of skill definitions for my class
allClassSkills: {},     // Map of class_id -> skill defs (for party members)
```

Update `MATCH_START` reducer:
```js
case 'MATCH_START': {
  // ... existing logic ...
  const myClassId = action.payload.players?.[state.playerId]?.class_id;
  const classSkills = action.payload.class_skills?.[myClassId] || [];
  return {
    ...state,
    classSkills,
    allClassSkills: action.payload.class_skills || {},
    // ... rest unchanged
  };
}
```

Update `TURN_RESULT` reducer — add combat log entries for skill actions:
```js
// In the action log loop:
if (act.action_type === 'skill' && act.success) {
  logType = act.killed ? 'kill' : act.heal_amount ? 'heal' : 'damage';
}
```

Update queue display text for `action_type === 'skill'`:
```js
: action.action_type === 'skill'
? `${action.skill_icon || '✨'} ${action.skill_name || action.skill_id}`
```

#### 5. Update `action_queued` response

Include skill info in the queue response so the ActionBar/SkillBar can display queued skills:

```json
{
  "type": "action_queued",
  "action_type": "skill",
  "skill_id": "heal",
  "queue": [
    { "action_type": "move", "target_x": 5, "target_y": 3 },
    { "action_type": "skill", "skill_id": "heal", "target_x": 6, "target_y": 3 }
  ]
}
```

### Tests to Write
- WS accepts `action_type: "skill"` with valid `skill_id`
- WS rejects `action_type: "skill"` without `skill_id` (or invalid skill_id)
- `match_start` payload includes `class_skills` data
- `turn_result` payload includes `cooldowns` with skill cooldowns
- `turn_result` payload includes `active_buffs`
- Queue response includes `skill_id` for skill actions
- Backward compat — existing WS tests pass

### Files Modified
| File | Change |
|------|--------|
| `server/app/services/websocket.py` | Validate `skill_id` on skill actions, include `skill_id` in all queue serialization points (action_queued, queue_updated, remove_last, party_member_selected, batch_actions) |
| `server/app/core/match_manager.py` | Add `class_skills` to `get_match_start_payload`, add `active_buffs` to `get_players_snapshot` |
| `client/src/context/GameStateContext.jsx` | Add `classSkills`, `allClassSkills` to state; update MATCH_START, TURN_RESULT reducers; skill action log entries, heal/damage floaters for skills |
| `client/src/components/ActionBar/ActionBar.jsx` | Add skill queue display text, skill action mode hint |
| `client/src/components/Arena/Arena.jsx` | Add skill queue tile visualization |
| `server/tests/test_ws_skills.py` | **New file** — 31 tests covering WS skill validation, match_start class_skills, snapshot active_buffs, queue skill_id, backward compat |

### Acceptance Criteria
- [x] Client can send `{ type: "action", action_type: "skill", skill_id: "heal", target_x: 5, target_y: 3 }`
- [x] Server validates skill_id presence and validity for skill actions
- [x] Server queues skill actions and broadcasts results
- [x] `match_start` includes class skill definitions for all classes in the match
- [x] Client state tracks available skills, cooldowns, and active buffs
- [x] Queue display shows skill name/icon
- [x] All queue serialization points include skill_id (action_queued, queue_updated, remove_last, batch, party_member_selected)
- [x] turn_result payload includes active_buffs for all players
- [x] Backward compat — all existing tests pass (858 total: 827 existing + 31 new)

### Implementation Notes (Phase 6C — completed 2026-02-14)
- Added `skill_id` validation in WS handler: rejects skill actions without `skill_id` or with unknown `skill_id`
- Added `class_skills` to `match_start` payload — maps each class in the match to an array of skill definitions with `skill_id`, `name`, `icon`, `cooldown_turns`, `targeting`, `range`, `description`, `requires_line_of_sight`
- Added `active_buffs` to `get_players_snapshot()` — serialized as `list` in turn_result player data
- Updated all 5 queue serialization points in `websocket.py` to include `skill_id`:
  - `action_queued` (single action), `queue_updated` (after tick), `remove_last`, `batch_actions`, `select_party_member`
- Updated client `GameStateContext.jsx`:
  - Added `classSkills` and `allClassSkills` to initial state
  - MATCH_START reducer extracts `class_skills` from payload based on player's class_id
  - TURN_RESULT reducer handles skill action log entries (heal → green 'heal', damage → purple 'damage', buff → 'system', teleport → 'move', kill → 'kill')
  - Skill damage floaters: green `+N` for heals, purple `-N` for skill damage
- Updated ActionBar queue display: skill actions show as `✨ skill_id → (x, y)`
- Updated ActionBar mode hint: skill modes show "Click a valid target for your skill"
- Updated Arena queue visualization: skill target tiles rendered in queue preview
- 31 new tests in `test_ws_skills.py` across 7 test classes
- Full backward compat verified: 858 tests passing, 0 failures; client builds cleanly

---

## Sub-Phase 6D: SkillBar UI & Canvas Targeting

### Goal
Build a dedicated SkillBar component that displays the player's class skills with cooldown overlays, and extend the canvas click handler to support skill targeting modes.

### Tasks

#### 1. Create `SkillBar.jsx` component

**File (new):** `client/src/components/SkillBar/SkillBar.jsx`

A horizontal bar of skill buttons, separate from the ActionBar. Each button shows:
- Skill icon (emoji for now)
- Skill name
- Cooldown overlay (grayed out + number when on cooldown)
- Hotkey number (1, 2, 3, 4)
- Active highlight when the skill's targeting mode is selected
- Tooltip on hover with description, cooldown, targeting info

```
┌──────────────────────────────────┐
│ Skills                           │
│ [1: 💚 Heal (4)] [2: ⚔️⚔️ DblStrike] │
│                                  │
│ Click a skill, then click target │
└──────────────────────────────────┘
```

When a skill button is clicked:
- `dispatch({ type: 'SET_ACTION_MODE', payload: 'skill_heal' })` (pattern: `skill_<skill_id>`)
- The canvas highlights valid targets based on `targeting` mode:
  - `self` — highlights the player's own tile
  - `ally_or_self` — highlights self + adjacent allies
  - `enemy_adjacent` — highlights adjacent enemy tiles
  - `enemy_ranged` — highlights enemies in range with LOS (same as ranged attack)
  - `empty_tile` — highlights valid empty tiles in range with LOS

#### 2. Extend `ArenaRenderer.js` highlight logic

Add skill targeting highlights in the canvas renderer:
- New highlight color for skills (e.g., blue/purple for ally skills, orange for offensive)
- Re-use existing `validMoves`, `attackHighlights`, `rangedHighlights` patterns
- Add a `skillHighlights` computed set based on the active skill's targeting type

#### 3. Extend `Arena.jsx` click handler

When `actionMode` starts with `'skill_'`:
- Extract `skill_id` from the mode string
- Validate the clicked tile against the skill's targeting requirements
- Send: `{ type: 'action', action_type: 'skill', skill_id: 'heal', target_x, target_y }`
- For `self` targeting skills: auto-target self on click (no tile selection needed)

#### 4. Update ActionBar queue display

Add skill action rendering to the queue list:

```jsx
: action.action_type === 'skill'
? `${skillIcon} ${skillName} → (${action.target_x}, ${action.target_y})`
```

#### 5. Cooldown display in SkillBar

Each skill button checks `myPlayer.cooldowns[skill_id]` and shows:
- A grayed overlay with the remaining turns number
- Disabled state (no click)
- Tooltip: "On cooldown (X turns remaining)"

#### 6. Buff indicator on HUD

Show active buffs on the HUD below cooldowns:

```
🔷 War Cry — 2x melee (1 turn left)
```

### Files Created/Modified
| File | Change |
|------|--------|
| `client/src/components/SkillBar/SkillBar.jsx` | **New file** — skill bar component |
| `client/src/components/Arena/Arena.jsx` | Import SkillBar, add to sidebar, extend click handler for `skill_*` modes |
| `client/src/canvas/ArenaRenderer.js` | Add skill targeting highlight rendering |
| `client/src/components/HUD/HUD.jsx` | Add active buff indicators |
| `client/src/styles/main.css` | SkillBar styles: buttons, cooldown overlay, hotkey labels, buff indicators |

### Acceptance Criteria
- [x] SkillBar renders class-appropriate skill buttons
- [x] Clicking a skill enters targeting mode with correct highlight pattern
- [x] Clicking a valid target queues the skill action
- [x] Cooldown overlay shows remaining turns, disables button
- [x] Active buffs display on HUD with remaining duration
- [x] Queue display shows skill name and target
- [x] Self-targeting skills auto-target on button click (or single click on self)
- [x] Works for party-controlled units (skill bar updates to show their skills)

### Implementation Notes (Phase 6D — completed 2026-02-14)
- Created `client/src/components/SkillBar/SkillBar.jsx` — dedicated skill bar component with:
  - Class-appropriate skill buttons with icon, name, and hotkey number (1-4)
  - Cooldown overlay: grayed button with remaining turns number, disabled click
  - Tooltip with skill description, cooldown, targeting mode, and range
  - Self-targeting skills (War Cry) auto-queue immediately on button click
  - Other skills toggle `skill_<skill_id>` action mode for canvas targeting
  - Party control support: shows controlled ally's class skills from `allClassSkills`
  - Contextual targeting hint text below buttons
- Extended `Arena.jsx` with:
  - `activeSkillDef` useMemo — resolves current skill definition from action mode
  - `skillHighlights` useMemo — computes valid target tiles based on skill targeting type:
    - `self`: highlights own tile
    - `ally_or_self`: highlights self + adjacent alive allies
    - `enemy_adjacent`: highlights adjacent enemies
    - `enemy_ranged`: highlights enemies within range (uses unit's ranged_range if skill range is 0)
    - `empty_tile`: highlights unoccupied, non-obstacle tiles within range
  - Skill click handler: validates click against `skillHighlights`, sends `{ type: 'action', action_type: 'skill', skill_id, target_x, target_y }`
  - SkillBar rendered in sidebar between ActionBar and Inventory
  - `skillHighlights` passed to ArenaRenderer and included in render effect dependencies
- Extended `ArenaRenderer.js`:
  - Added `skillHighlights` parameter to `renderFrame()`
  - Renders skill target highlights in purple (`rgba(160, 80, 240, 0.3)`) — distinct from move (blue), attack (red), ranged (orange)
- Extended `HUD.jsx` with active buff indicators:
  - Displays active buffs below cooldown section with icon, buff name, effect description, and remaining turns
  - `formatBuffName()` and `formatBuffEffect()` helper functions for readable buff display
  - Supports melee/ranged damage multiplier and damage reduction buff types
- Added CSS styles in `main.css`:
  - `.skill-bar`, `.btn-skill`, `.skill-hotkey`, `.skill-icon`, `.skill-name` — button layout and styling
  - `.skill-cooldown-overlay` — absolute-positioned dark overlay with red cooldown number
  - `.btn-skill.active` — purple glow highlight when targeting mode is active
  - `.skill-targeting-hint` — italic hint text for current targeting mode
  - `.hud-buffs`, `.buff-indicator`, `.buff-icon`, `.buff-name`, `.buff-detail` — buff display in HUD
- Full backward compat verified: 830 tests passing, 0 failures; client builds cleanly (0 errors)

---

## Sub-Phase 6E: Dungeon GUI Reorganization

### Goal
Restructure the dungeon in-match layout so everything fits in a single browser viewport without scrolling. Consolidate redundant panels and create a cleaner, more intuitive layout.

### Current Problems
1. **Two redundant party displays** — HUD has a player list AND PartyPanel shows party members
2. **Vertical overflow** — HUD + PartyPanel + ActionBar + SkillBar + Inventory + CombatLog + Leave button exceeds viewport height
3. **Action buttons sprawl** — Move, Attack, Ranged, Wait, Interact, Loot, Potion, + now Skills all compete for space
4. **Sidebar too narrow** — 220–280px forces compact layouts that are hard to read

### Proposed Layout

```
┌─────────────────────────────────────────────────────────┐
│                    HEADER BAR (compact)                  │
│  Turn: 12  │  Timer ████░░  │  Your HP ██████░░  87/120 │
├───────────────────────────┬─────────────────────────────┤
│                           │  PARTY PANEL (compact)      │
│                           │  [Hero1] ██████ 80/100  Q:3 │
│                           │  [Hero2] ████░░ 45/100  Q:1 │
│     CANVAS (map)          │  [Hero3] ██░░░░ 20/100      │
│     (fills available      │─────────────────────────────│
│      vertical space)      │  COMBAT LOG (scrollable)    │
│                           │  Turn 12: You hit Demon...  │
│                           │  Turn 12: Demon hit you...  │
│                           │  Turn 11: You opened door   │
├───────────────────────────┴─────────────────────────────┤
│                    BOTTOM BAR                            │
│  [🏃Move][⚔️Atk][🏹Rng][⏳Wait][🚪Int][🎒Loot][🧪Pot] │
│  [1:💚Heal][2:⚔️⚔️DblStrike][3:📯WarCry]  Queue: 3/10 │
│  Buff: 🔷 War Cry (1 turn)     [↩Undo] [✕Clear] [Leave]│
└─────────────────────────────────────────────────────────┘
```

### Tasks

#### 1. Restructure Arena.jsx layout

Change from `sidebar` layout to a 3-zone layout:
- **Top bar** — Compact HUD: turn number, timer bar, HP bar, active buffs (single horizontal row)
- **Middle** — Canvas (left, fills space) + Right panel (Party + Combat Log, stacked)
- **Bottom bar** — Unified action bar: core actions + skill buttons + queue info + controls

Use CSS grid or flexbox:
```css
.arena {
  display: grid;
  grid-template-rows: auto 1fr auto;
  grid-template-columns: 1fr 280px;
  height: 100vh;
  gap: 4px;
}
.arena-header { grid-column: 1 / -1; }      /* spans full width */
.arena-canvas-area { grid-column: 1; }       /* left */
.arena-right-panel { grid-column: 2; }       /* right */
.arena-bottom-bar { grid-column: 1 / -1; }  /* spans full width */
```

#### 2. Create compact `HeaderBar.jsx`

**File (new):** `client/src/components/HeaderBar/HeaderBar.jsx`

A single-row header containing:
- Turn number
- Turn timer (compact progress bar)
- Player HP bar with number
- Active buff icons with remaining turns
- Class icon + name
- Mode indicator (e.g., "Dungeon" / "Arena")

Replaces the top portion of the current HUD.

#### 3. Consolidate PartyPanel

Remove the player list from HUD (it's redundant with PartyPanel). PartyPanel becomes the single source of party/player info in the right panel. If no party members, show a compact "Solo" indicator.

#### 4. Merge ActionBar + SkillBar into unified BottomBar

**File (new):** `client/src/components/BottomBar/BottomBar.jsx`

A horizontal bar at the bottom of the screen containing:
- **Core actions** (left group): Move, Attack, Ranged, Wait — always visible
- **Context actions** (middle group): Interact, Loot, Potion — shown when relevant (dungeon mode, items available)
- **Skills** (right group): Class skill buttons with cooldown overlays and hotkey numbers
- **Queue info** (far right): Queue count (3/10), Undo, Clear, Leave

All in a single horizontal strip, similar to an MMO hotbar.

#### 5. Compact CombatLog

Reduce CombatLog max height (e.g., 150px), keep it scrollable, position in the right panel below PartyPanel.

#### 6. Inventory as overlay/modal

Move Inventory from the sidebar to a toggle overlay (click a bag icon on the bottom bar to open/close). This prevents it from consuming sidebar space permanently.

#### 7. Update CSS

Rewrite `.arena` layout in `main.css` from flexbox row to CSS grid. Ensure:
- No scrolling at 1080p+ resolution
- Canvas scales to fill available space
- Right panel has a sensible min/max width
- Bottom bar is compact and doesn't wrap

### Files Created/Modified
| File | Change |
|------|--------|
| `client/src/components/HeaderBar/HeaderBar.jsx` | **New file** — compact top bar |
| `client/src/components/BottomBar/BottomBar.jsx` | **New file** — unified action + skill bar |
| `client/src/components/Arena/Arena.jsx` | Restructure layout to 3-zone grid |
| `client/src/components/HUD/HUD.jsx` | Slim down to just the data HeaderBar needs (or deprecate) |
| `client/src/components/PartyPanel/PartyPanel.jsx` | Minor: becomes the sole party display |
| `client/src/components/Inventory/Inventory.jsx` | Convert to toggle overlay |
| `client/src/styles/main.css` | Full layout rewrite for `.arena` and related selectors |

### Acceptance Criteria
- [ ] Entire dungeon game view fits in one viewport (no scrollbar) at 1920×1080
- [ ] Single party display (no redundancy)
- [ ] All core actions + skills accessible from the bottom bar
- [ ] Combat log visible without scrolling the page (internal scroll only)
- [ ] Inventory opens as overlay, doesn't consume sidebar space
- [ ] Canvas fills available space (responsive)
- [ ] Arena mode layout also works (fewer actions shown, same structure)
- [ ] No functionality lost from the reorganization

---

## Sub-Phase 6F: Keyboard Shortcuts

### Goal
Add keyboard shortcut support so players can trigger actions and skills without clicking buttons.

### Keybinding Map

| Key | Action | Context |
|-----|--------|---------|
| `Q` | Move mode | Always |
| `W` | Attack mode | Always |
| `E` | Ranged Attack mode | When available |
| `R` | Interact mode | Dungeon only |
| `F` | Loot | When items available |
| `T` | Use Potion | When potions available |
| `Space` | Wait | Always |
| `1` | Skill slot 1 | When skill available |
| `2` | Skill slot 2 | When skill available |
| `3` | Skill slot 3 | When skill available |
| `4` | Skill slot 4 | When skill available |
| `Escape` | Cancel current mode | Always |
| `Z` | Undo last queued action | When queue not empty |
| `X` | Clear queue | When queue not empty |
| `I` | Toggle inventory | Dungeon only |
| `Tab` | Cycle party member control | When party exists |

### Tasks

#### 1. Create `useKeyboardShortcuts` hook

**File (new):** `client/src/hooks/useKeyboardShortcuts.js`

A custom hook that:
- Listens for `keydown` events on the document
- Maps keys to action dispatches / skill activations
- Respects disabled states (dead, cooldown, queue full)
- Only active during `matchStatus === 'in_progress'`
- Does NOT fire when typing in chat or other input fields

```js
export default function useKeyboardShortcuts({ onAction, classSkills, ... }) {
  useEffect(() => {
    const handler = (e) => {
      if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') return;
      // ... map keys to actions
    };
    document.addEventListener('keydown', handler);
    return () => document.removeEventListener('keydown', handler);
  }, [deps]);
}
```

#### 2. Show keybind hints on buttons

Add small keybind labels to each button in the BottomBar:

```
[Q 🏃Move] [W ⚔️Atk] [E 🏹Rng] [Space ⏳Wait] [1 💚Heal] [2 ⚔️⚔️DblStrike]
```

#### 3. Self-targeting shortcut

For `self`-targeting skills (like War Cry), pressing the hotkey auto-queues immediately without requiring a target click.

### Files Created/Modified
| File | Change |
|------|--------|
| `client/src/hooks/useKeyboardShortcuts.js` | **New file** — keyboard shortcut hook |
| `client/src/components/Arena/Arena.jsx` | Wire up the hook |
| `client/src/components/BottomBar/BottomBar.jsx` | Add keybind labels to buttons |
| `client/src/styles/main.css` | Keybind label styling |

### Acceptance Criteria
- [ ] All listed keybindings work during active match
- [ ] Keybinds respect disabled states (dead, cooldown, queue full)
- [ ] Keybinds don't fire when typing in chat/input
- [ ] Self-targeting skills auto-queue on keypress
- [ ] Keybind hints visible on all action/skill buttons
- [ ] `Escape` cancels current targeting mode
- [ ] `Tab` cycles through party members

---

## Sub-Phase 6G: AI Skill Usage

### Goal
Enable AI enemies and party member AI to use skills intelligently during their turns.

### Tasks

#### 1. Extend `ai_behavior.py`

Add skill selection logic to AI decision-making:

```python
def choose_ai_action(unit, players, obstacles, ...):
    # Existing: move, melee, ranged decisions
    # NEW: Check if unit has available skills and conditions are met
    #   - Boss enemies could use a signature skill on cooldown
    #   - Healer AI allies prioritize healing wounded allies
    #   - Aggressive AI uses damage skills when in range
```

#### 2. Assign skills to enemy types

Extend `enemies_config.json` to include enemy skills:

```json
{
  "demon": {
    "skills": ["war_cry"],
    "skill_chance": 0.3
  },
  "skeleton": {
    "skills": [],
    "skill_chance": 0
  },
  "undead_knight": {
    "skills": ["double_strike"],
    "skill_chance": 0.4
  }
}
```

#### 3. AI party member skill usage

When a party member is under AI control (not player-controlled), the AI should:
- Confessor AI: Use Heal when any ally is below 50% HP and heal is off cooldown
- Crusader AI: Use War Cry before engaging, then Double Strike when adjacent to enemy
- Ranger AI: Use Power Shot when in range and off cooldown
- Hexblade AI: Use Shadow Step to close distance, then Double Strike

#### 4. Boss special skills (future-ready)

Structure the system so bosses can have unique skills not available to players. The `allowed_classes` field in skills_config already supports this — a boss-only skill would have `"allowed_classes": []` and be assigned via `enemies_config.json` directly.

### Files Modified
| File | Change |
|------|--------|
| `server/app/core/ai_behavior.py` | Add skill selection logic to AI decision trees |
| `server/configs/enemies_config.json` | Add `skills` and `skill_chance` to enemy definitions |

### Acceptance Criteria
- [ ] AI enemies use assigned skills at appropriate times
- [ ] AI party members under autonomy use their class skills intelligently
- [ ] Confessor AI prioritizes healing wounded allies
- [ ] Skill usage respects cooldowns
- [ ] AI doesn't use skills that would be wasted (heal on full HP unit)
- [ ] Backward compat — AI without skills behaves identically to current

---

## Implementation Order & Dependencies

```
6A (Models & Config)
 └──▶ 6B (Turn Resolver)
       └──▶ 6C (WS Protocol & Client State)
             └──▶ 6D (SkillBar UI)
                   │
                   ├──▶ 6F (Keyboard Shortcuts)  ← can start when 6D is done
                   │
                   └──▶ 6G (AI Skills)            ← can start when 6B is done
                   
6E (GUI Reorganization)  ← independent of 6A-6D, can run in parallel
                          ← but easiest after 6D since SkillBar is part of the new layout
```

**Recommended order for a single developer:** 6A → 6B → 6C → 6D → 6E → 6F → 6G

**If parallelizing:** One dev on 6A→6B→6C→6D, another on 6E (GUI). Then 6F and 6G can be split.

---

## Testing Strategy

| Sub-Phase | Test Type | Expected New Tests |
|-----------|-----------|-------------------|
| 6A | Unit: config parsing, model validation | ~15 |
| 6B | Unit + integration: skill effects, buff system, turn resolver | ~30 |
| 6C | Integration: WS protocol, client state | ~10 |
| 6D | Manual: UI interaction, targeting, visual | Manual QA |
| 6E | Manual: layout, responsiveness, no scroll | Manual QA |
| 6F | Manual: keybind verification | Manual QA |
| 6G | Unit: AI decision trees with skills | ~15 |

**Running total after Phase 6:** ~700 tests (627 existing + ~70 new)

### Backward Compatibility Rules
- All existing 627 tests must pass after each sub-phase
- Arena mode (no skills, no dungeon) must be completely unaffected
- Players without a class (legacy mode) have no skills — SkillBar is hidden
- AI units without skills behave exactly as they do today
- Existing action types (move, attack, ranged, etc.) are unchanged

---

## Future Considerations (Phase 7+)

These are explicitly **not** in Phase 6 scope but the architecture should not block them:

- **Mana system** — `mana_cost` field exists in skill config, PlayerState would get `mana` / `max_mana`
- **More skills per class** — Config-driven, no code changes needed to add skills
- **Skill trees / leveling** — Would extend the Hero model with learned skills
- **DoT effects** (Bleed, Poison) — Would use the `active_buffs` system with a "damage" effect type
- **AoE skills** — Would need a `targeting: "area"` mode with radius
- **Rare/Unique items that grant skills** — Item model already has extensible `stat_bonuses`
- **Proc-on-hit effects** — Could hook into combat.py damage resolution
