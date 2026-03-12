# Phase 10G — Skill & Ability Auto-Target Pursuit

## Overview

Phase 10 (10A–10F) added persistent melee pursuit: right-click an enemy → the server auto-generates chase/attack actions every tick until the target dies or the player cancels. This works great for basic melee, but **skills and abilities are completely excluded** from the system.

**The Problem:** Using a skill currently requires the player to:
1. Press a skill button → enter targeting mode (highlights show only targets **already in range**)
2. Left-click a highlighted tile to queue the skill

If the enemy is out of range, zero highlights appear — the player can't do anything. They must manually walk closer, then try again. In combat this is extremely clunky — you're fighting your UI instead of fighting enemies.

**Goal — "Target-first, skill-second" flow:**
1. **Left-click a unit** → that unit becomes your **selected target** (enemy or friendly)
2. **Press skill/ability button** →
   - If already in range → **cast immediately** on the selected target
   - If out of range → **auto-path to skill range → auto-cast on arrival**
3. Works for **all offensive abilities** (Double Strike, Power Shot) AND **friendly-target abilities** (Heal)
4. `self`-targeting skills (War Cry) and `empty_tile` skills (Shadow Step) are unaffected — they don't need a target

This extends the Phase 10 auto-target system with a `skill_id` component so the server knows to generate skill actions (not just melee attacks) when the player reaches the appropriate range.

---

## Current State (Diagnosed)

### How Skills Work Now

**Client side** ([client/src/components/BottomBar/BottomBar.jsx](../../client/src/components/BottomBar/BottomBar.jsx) — `handleSkillClick()`):
1. Player clicks skill button (or presses hotkey 1-5)
2. If `self`-targeting → immediately queues skill action at own position
3. Otherwise → sets `actionMode` to `skill_{skill_id}`, entering targeting mode

**Client side** ([client/src/components/Arena/Arena.jsx](../../client/src/components/Arena/Arena.jsx) — `skillHighlights` + `handleCanvasClick()`):
1. `activeSkillDef` resolves the skill definition from `actionMode` string
2. `skillHighlights` computes valid target tiles based on targeting type + range:
   - `ally_or_self` → own tile + allies within range (Chebyshev ≤ skill range)
   - `enemy_adjacent` → adjacent enemies (Chebyshev ≤ 1)
   - `enemy_ranged` → enemies within Euclidean range (uses unit's `ranged_range` if skill range = 0)
   - `empty_tile` → unoccupied tiles within Euclidean range with LOS
3. Left-click on highlighted tile → sends `{ type: 'action', action_type: 'skill', skill_id, target_x, target_y }`

**Server side** ([server/app/core/turn_resolver.py](../../server/app/core/turn_resolver.py) — Phase 1.9):
1. Skill actions resolve after movement but before ranged/melee
2. Validates via `can_use_skill()` in [server/app/core/skills.py](../../server/app/core/skills.py): class restriction, cooldown, alive
3. Dispatches to `resolve_skill_action()` which handles each effect type (heal, melee_damage, ranged_damage, buff, teleport)

### How Auto-Target Works Now (Phase 10)

**Server model** ([server/app/models/player.py](../../server/app/models/player.py) — line 62):
```python
auto_target_id: str | None = None  # Only stores target — no skill info
```

**Server tick** ([server/app/core/match_manager.py](../../server/app/core/match_manager.py) — `generate_auto_target_action()` at line 719):
1. Validates target alive + different team
2. If adjacent → generates `ActionType.ATTACK` (melee)
3. If not adjacent → A* pathfind → `ActionType.MOVE` one step (or `INTERACT` for doors)
4. If unreachable → clears auto-target

### The Gap

| Limitation | Detail |
|-----------|--------|
| **No skill pathfinding** | `generateSmartActions()` can't do "path to within range X then cast skill Y" |
| **Auto-target is melee-only** | `generate_auto_target_action()` only produces `MOVE` or `ATTACK` — no `SKILL` |
| **Skill targeting is range-gated** | If enemy is out of range, no highlights appear — player is stuck |
| **No pending skill state** | No `auto_skill_id` field exists — server can't remember "cast this skill when in range" |
| **No friendly auto-target** | `set_auto_target()` enforces `target.team != player.team` — blocks Heal targeting |

### Relevant Files

| File | Role | Changes Needed |
|------|------|----------------|
| `server/app/models/player.py` | `PlayerState` | Add `auto_skill_id` field |
| `server/app/core/match_manager.py` | Auto-target helpers + action generation | Extend for skill awareness |
| `server/app/core/skills.py` | `can_use_skill()`, `resolve_skill_action()` | Reference only — no changes |
| `server/app/services/websocket.py` | WS handlers + `match_tick()` Step 3.5 | Extend messages + tick logic |
| `server/configs/skills_config.json` | Skill definitions (targeting, range) | Reference only — no changes |
| `client/src/components/BottomBar/BottomBar.jsx` | Skill button handler (`handleSkillClick`) | Add selected-target-aware logic |
| `client/src/components/Arena/Arena.jsx` | Canvas click handler, skill highlights | Add left-click target selection |
| `client/src/context/GameStateContext.jsx` | Client state (reducers) | Add `selectedTargetId`, `autoSkillId` |
| `client/src/canvas/ArenaRenderer.js` | Canvas rendering | Selected-target visual indicator |
| `client/src/components/HUD/HUD.jsx` | HUD auto-target display | Show skill info in target frame |
| `client/src/App.jsx` | WS message routing | Handle skill auto-target messages |
| `docs/websocket-protocol.md` | Protocol docs | Document new message fields |

### Skills Reference

| Skill | `targeting` | `range` | LOS | Effect | Applicable? |
|-------|-----------|---------|-----|--------|-------------|
| Heal | `ally_or_self` | 3 | no | heal 30 HP | **YES** — path to ally → cast |
| Double Strike | `enemy_adjacent` | 1 | no | 2 hits × 0.6× melee | **YES** — path to adjacent → cast |
| Power Shot | `enemy_ranged` | 0 (use `ranged_range`) | yes | 1.8× ranged damage | **YES** — path to ranged range → cast |
| War Cry | `self` | 0 | no | buff: 2× melee, 2 turns | **NO** — already auto-casts on self |
| Shadow Step | `empty_tile` | 3 | yes | teleport | **NO** — targets a tile, not a unit |

---

## Architecture Decision

### Why Extend Server-Side Auto-Target (not client-side queuing)

The Phase 10 architecture decision already established server-side auto-target as the correct approach. The same reasoning applies doubly for skills:

| Approach | Why Not |
|----------|---------|
| Client computes "move to range + skill" batch | Stale coordinates — target moves, skill misses. Must recompute every tick. |
| Client re-queues skill every tick | Race conditions, doubled WS traffic, fragile timing |
| **Extend server auto-target with skill (chosen)** | Server has live positions, computes range in real-time, produces correct action per tick, minimal WS traffic |

The extension is clean: add `auto_skill_id` alongside `auto_target_id`, and modify `generate_auto_target_action()` to check skill range instead of adjacency and produce `SKILL` actions instead of `ATTACK`.

---

## Phased Implementation Plan

### Phase 10G-1 — Server Model: Add `auto_skill_id`
**Priority: FOUNDATION**

**File:** `server/app/models/player.py`

Add a new optional field to `PlayerState` next to `auto_target_id`:

```python
    # Phase 10A: Auto-target — persistent melee pursuit target
    # When set, the server generates chase/attack actions each tick if the player's queue is empty.
    # Cleared when: target dies, player issues a new command, player cancels, target unreachable.
    auto_target_id: str | None = None
    # Phase 10G: Skill auto-target — when set alongside auto_target_id, the server generates
    # SKILL actions instead of ATTACK when in range. None = melee pursuit (Phase 10 default).
    auto_skill_id: str | None = None
```

**Constraints:**
- `auto_skill_id` is only meaningful when `auto_target_id` is also set
- When `auto_target_id` is cleared, `auto_skill_id` must also be cleared
- Default `None` — melee pursuit behavior is unchanged

**File:** `server/app/core/match_manager.py`

Update existing helpers:

```python
def set_auto_target(match_id, player_id, target_id, skill_id=None) -> bool | str:
    """Set a persistent auto-target for a player, optionally with a skill.

    New validations when skill_id is provided:
    - Skill exists in config
    - Player's class can use the skill
    - Skill targeting is compatible with target:
        - 'enemy_adjacent' or 'enemy_ranged' → target must be on different team
        - 'ally_or_self' → target must be on same team OR self
    - Skill is NOT on cooldown (warning: ok to set, will approach while cooling)

    When skill_id is provided and target is an ally/self, skip the existing
    "different team" validation (required for Heal).
    """
```

```python
def clear_auto_target(match_id, player_id) -> None:
    """Clear auto_target_id AND auto_skill_id for a player."""
    # Existing clear logic, plus: player.auto_skill_id = None
```

**Everywhere `auto_target_id` is cleared** (in `queue_action()`, death cleanup, etc.), also clear `auto_skill_id`.

**Estimated scope:** ~5 lines model, ~30 lines match_manager changes

---

### Phase 10G-2 — Server: Extend `generate_auto_target_action()` for Skills
**Priority: CORE — The beating heart of the feature**

**File:** `server/app/core/match_manager.py`

Modify `generate_auto_target_action()` (currently at line 719). The key change is in the "action decision" logic:

```python
def generate_auto_target_action(
    match_id, player_id, all_units,
    grid_width, grid_height, obstacles,
    door_tiles=None,
) -> PlayerAction | None:
    """Generate a chase/attack/skill action for a player with an active auto-target.

    Extended decision logic (Phase 10G):
      1. Validate target (alive, appropriate team based on skill targeting type)
      2. If auto_skill_id is set:
         a. Resolve effective range for the skill
         b. If skill on cooldown AND not in range → MOVE toward target (close gap while waiting)
         c. If skill on cooldown AND in range → WAIT (stay in position, wait for cooldown)
         d. If in range (and off cooldown):
            - For skills requiring LOS: check LOS → if blocked, MOVE to reposition
            - Return SKILL action with target's current coordinates
         e. If not in range → A* toward a tile within skill range → MOVE one step
      3. If auto_skill_id is NOT set (existing behavior):
         a. If adjacent → ATTACK
         b. If not adjacent → MOVE toward target
      4. If unreachable → clear auto-target, return None
    """
```

#### Range Calculation Logic

Each targeting type resolves to an effective range:

```python
def _get_skill_effective_range(skill_def: dict, player: PlayerState) -> int:
    """Determine the effective range for a skill.

    - 'enemy_adjacent' → 1 (Chebyshev)
    - 'enemy_ranged' with range=0 → player.ranged_range (from class config)
    - 'enemy_ranged' with range>0 → skill.range
    - 'ally_or_self' → skill.range (Chebyshev)
    """
```

#### "In Range" Check

```python
def _is_in_skill_range(player_pos, target_pos, effective_range, targeting_type) -> bool:
    """Check if player is within skill range of target.

    - 'enemy_adjacent' → Chebyshev distance ≤ 1 (same as is_adjacent)
    - 'enemy_ranged' → Euclidean distance ≤ effective_range
    - 'ally_or_self' → Chebyshev distance ≤ effective_range
    """
```

#### A* Goal for Skills

When not in range, A* needs to pathfind to **a tile within skill range** of the target, not necessarily adjacent. This requires a modified goal:

```python
# For melee / enemy_adjacent: goal = any tile adjacent to target (existing)
# For ranged skills (range > 1): goal = any tile within range of target
# The A* destination is the target tile, but we stop early when we reach a tile within range
```

**Implementation approach:** Use the existing `a_star()` function to path toward the target, but check each step of the returned path — stop at the first tile that is within skill range. This avoids modifying the core A* algorithm.

```python
# Path toward target
path = a_star(player_pos, target_pos, grid_width, grid_height, obstacles, occupied, door_tiles)
if not path:
    clear_auto_target(match_id, player_id)
    return None

# For skills with range > 1, we don't need to reach the target — just get in range
if effective_range > 1:
    # Walk along the path until we find a tile in range
    # The next step is always path[0] — we just move one step per tick
    pass  # Standard one-step movement still works; the "in range" check above
          # will trigger the SKILL action once we're close enough

next_step = path[0]
# ... existing door/move logic
```

#### LOS Check for Ranged Skills

Power Shot requires line-of-sight. When in range but LOS is blocked:
- Don't cast (the skill would fail on the server anyway)
- Move to reposition (pick a step along the A* path)
- The natural A* movement will often resolve LOS issues as the player approaches

```python
if skill_def.get('requires_line_of_sight', False):
    from app.core.fov import has_line_of_sight
    if not has_line_of_sight(player_pos, target_pos, obstacles, grid_width, grid_height):
        # In range but no LOS — move one step toward target to try to get clear LOS
        # ... existing pathfind + move logic
```

#### Cooldown Handling

The skill might be on cooldown when first set (the player wants to queue it up), or it might go on cooldown after a cast. Behavior:

| State | In Range? | Action |
|-------|-----------|--------|
| Off cooldown | Yes | **SKILL** (cast!) |
| Off cooldown | No | **MOVE** toward target |
| On cooldown | Yes | **WAIT** (hold position, wait for cooldown) |
| On cooldown | No | **MOVE** toward target (close gap while cooling) |

After a successful cast, the key question: **should auto-target persist?** Yes — this allows repeated casting (e.g., Power Shot every 5 turns while chasing). The auto-target persists until:
- Target dies
- Player issues a new command
- Player explicitly cancels
- Target becomes permanently unreachable

#### Friendly Target Validation

For `ally_or_self` skills (Heal), the validation in step 1 must check `target.team == player.team` (same team) instead of the existing `target.team != player.team` (different team) check:

```python
# Determine expected team relationship from skill
if auto_skill_id:
    skill_def = get_skill(auto_skill_id)
    targeting = skill_def.get('targeting', '')
    if targeting == 'ally_or_self':
        # Friendly target — validate same team or self
        if target.team != player.team and target_id != player_id:
            clear_auto_target(match_id, player_id)
            return None
    else:
        # Enemy target — validate different team (existing)
        if target.team == player.team:
            clear_auto_target(match_id, player_id)
            return None
else:
    # No skill — melee pursuit, must be enemy (existing behavior)
    if target.team == player.team:
        clear_auto_target(match_id, player_id)
        return None
```

**Estimated scope:** ~80 lines in `generate_auto_target_action()`, ~20 lines helpers

---

### Phase 10G-3 — WebSocket Protocol Extensions
**Priority: HIGH — Connects client to server**

**Files:** `server/app/services/websocket.py`, `docs/websocket-protocol.md`

#### Extended `set_auto_target` Message

Client → Server:
```json
{
  "type": "set_auto_target",
  "target_id": "enemy_abc123",
  "unit_id": "player_id_or_party_member_id",
  "skill_id": "power_shot"
}
```

- `skill_id` is **optional** — omit for melee pursuit (existing behavior)
- When `skill_id` is provided, server validates:
  - Skill exists
  - Player's class can use it
  - Skill targeting is compatible with target team relationship
  - (Cooldown is NOT a blocker — player can approach while skill cools)

Server → Client (success):
```json
{
  "type": "auto_target_set",
  "unit_id": "player_id",
  "target_id": "enemy_abc123",
  "target_username": "Skeleton Warrior",
  "skill_id": "power_shot",
  "skill_name": "Power Shot"
}
```

- `skill_id` and `skill_name` are only present when a skill was specified
- Existing melee auto-target responses are unchanged (no `skill_id` field)

#### Extended `auto_target_cleared` Notification

No changes needed — the `reason` field already covers relevant cases:
- `"target_died"` — target was eliminated
- `"unreachable"` — no path available
- `"cancelled"` — player manually cancelled
- `"new_command"` — player issued a different action

#### Extended `turn_result.auto_targets`

Currently: `{ "unit_id": "target_id" }`

Extended: `{ "unit_id": { "target_id": "enemy_abc", "skill_id": "power_shot" } }`

Or when no skill (melee): `{ "unit_id": { "target_id": "enemy_abc", "skill_id": null } }`

#### WS Handler Changes in `websocket.py`

In the `set_auto_target` handler (currently ~line 1137):
1. Read optional `skill_id` from message data
2. Pass to `set_auto_target(match_id, unit_id, target_id, skill_id=skill_id)`
3. Include `skill_id` and `skill_name` in response

In `match_tick()` Step 3.5 auto-target cleared notification:
- Include `skill_id` in the cleared message so client knows what was cancelled

**Estimated scope:** ~25 lines server WS, ~10 lines docs

---

### Phase 10G-4 — Client State: Selected Target & Skill Auto-Target
**Priority: HIGH — Foundation for client-side changes**

**Files:** `client/src/context/GameStateContext.jsx`, `client/src/App.jsx`

#### New Client State Fields

```javascript
// In GameStateContext initial state, add:
selectedTargetId: null,    // Unit currently soft-selected via left-click (enemy or ally)
                           // This is a CLIENT-ONLY concept — nothing sent to server
                           // until a skill button is pressed.
autoSkillId: null,         // Skill being auto-cast alongside autoTargetId
partyAutoSkills: {},       // { unitId: skillId } for party members
```

#### New Reducer Cases

```javascript
case 'SELECT_TARGET':
  // Left-click on a unit (enemy or friendly) with no action mode active
  return { ...state, selectedTargetId: action.payload.targetId };

case 'CLEAR_SELECTED_TARGET':
  return { ...state, selectedTargetId: null };

case 'AUTO_TARGET_SET':
  // Extended: also store skill_id if present
  if (action.payload.unit_id === state.playerId) {
    return {
      ...state,
      autoTargetId: action.payload.target_id,
      autoSkillId: action.payload.skill_id || null,
      selectedTargetId: null,  // Clear soft-selection when auto-target activates
    };
  } else {
    return {
      ...state,
      partyAutoTargets: { ...state.partyAutoTargets, [action.payload.unit_id]: action.payload.target_id },
      partyAutoSkills: { ...state.partyAutoSkills, [action.payload.unit_id]: action.payload.skill_id || null },
    };
  }

case 'AUTO_TARGET_CLEARED':
  // Extended: also clear skill_id
  if (action.payload.unit_id === state.playerId) {
    return { ...state, autoTargetId: null, autoSkillId: null };
  } else {
    const newTargets = { ...state.partyAutoTargets };
    const newSkills = { ...state.partyAutoSkills };
    delete newTargets[action.payload.unit_id];
    delete newSkills[action.payload.unit_id];
    return { ...state, partyAutoTargets: newTargets, partyAutoSkills: newSkills };
  }

case 'CLEAR_AUTO_TARGET':
  return { ...state, autoTargetId: null, autoSkillId: null };
```

#### App.jsx WS Message Handler Updates

The existing `auto_target_set` handler already dispatches `AUTO_TARGET_SET`. Extend the combat log message:

```javascript
case 'auto_target_set':
  dispatch({ type: 'AUTO_TARGET_SET', payload: data });
  if (data.skill_id) {
    dispatch({ type: 'ADD_COMBAT_LOG', payload: {
      type: 'system',
      message: `⚔ Auto-casting ${data.skill_name || data.skill_id} on: ${data.target_username || 'Unknown'}`
    }});
  } else {
    dispatch({ type: 'ADD_COMBAT_LOG', payload: {
      type: 'system',
      message: `⚔ Auto-targeting: ${data.target_username || 'Unknown'}`
    }});
  }
  break;
```

#### `TURN_RESULT` Sync

Update the turn result auto-target sync to also read `skill_id`:

```javascript
// In TURN_RESULT reducer, where auto_targets are synced:
if (action.payload.auto_targets) {
  const myTarget = action.payload.auto_targets[state.playerId];
  newState.autoTargetId = myTarget?.target_id || null;
  newState.autoSkillId = myTarget?.skill_id || null;
  // ... party member sync with skill_id
}
```

#### Clear `selectedTargetId` On Various Events

The soft-selected target should clear when:
- Action mode is activated (player is now using the existing targeting system)
- Match ends / match starts
- Player dies
- Escape key is pressed

**Estimated scope:** ~50 lines context, ~15 lines App.jsx

---

### Phase 10G-5 — Client: Left-Click Target Selection
**Priority: HIGH — The player-facing input change**

**Files:** `client/src/components/Arena/Arena.jsx`, `client/src/canvas/ArenaRenderer.js`

#### Left-Click on Unit (No Action Mode) → Select Target

In `handleCanvasClick` in `Arena.jsx`, add a new case at the **end** of the existing action mode chain (after all existing modes are checked):

```javascript
// In handleCanvasClick, when NO actionMode is active:
if (!actionMode) {
  const tileKey = `${tile.x},${tile.y}`;
  const occupant = occupiedMap[tileKey];
  if (occupant && occupant.pid !== effectiveUnitId) {
    // Left-clicked a unit (enemy or friendly) — soft-select as target
    dispatch({ type: 'SELECT_TARGET', payload: { targetId: occupant.pid } });
    return;  // Don't process as anything else
  } else {
    // Clicked empty tile or self — clear selection
    dispatch({ type: 'CLEAR_SELECTED_TARGET' });
  }
}
```

**Key interaction:** This only fires when `actionMode` is `null`. If the player is in a skill targeting mode, move mode, attack mode, etc. — the existing handling takes priority. This is the "idle click" behavior.

#### Visual Indicator for Selected Target

In `ArenaRenderer.js`, add a rendering pass for the `selectedTargetId`:

```javascript
// After drawing units, before drawing auto-target reticle:
if (selectedTargetId && players[selectedTargetId]) {
  const target = players[selectedTargetId];
  if (isVisible(target.position)) {
    drawSelectedTargetIndicator(ctx, target.position.x, target.position.y, tileSize);
  }
}
```

The indicator should be visually distinct from the auto-target reticle (Phase 10E):
- **Selected target** (soft selection): Thin white/yellow circle or highlight ring — "I'm looking at this unit"
- **Auto-target** (active pursuit): Pulsing red brackets — "I'm actively pursuing this unit"
- Both can be visible simultaneously during the transition from selection to pursuit

Suggested: A steady (non-pulsing) highlighted ring in a neutral color (white or gold) with slight transparency. Disappears when auto-target activates (since the pulsing red reticle replaces it).

#### Right-Click Should Also Set Selected Target

When the player right-clicks an enemy (existing melee pursuit), also update `selectedTargetId`:

```javascript
// In handleContextMenu, when result.intent === 'attack':
dispatch({ type: 'SELECT_TARGET', payload: { targetId: targetInfo.pid } });
```

This keeps the selection and auto-target in sync.

**Estimated scope:** ~25 lines Arena.jsx, ~20 lines ArenaRenderer.js

---

### Phase 10G-6 — Client: Skill Button with Selected Target
**Priority: HIGH — The key UX improvement**

**Files:** `client/src/components/BottomBar/BottomBar.jsx`, `client/src/components/Arena/Arena.jsx`

This is the core client change — when a skill button is pressed and `selectedTargetId` is set, determine if we can cast or need to auto-pursue.

#### Modified `handleSkillClick()` in BottomBar.jsx

```javascript
const handleSkillClick = useCallback((skill) => {
  if (isDead || queueFull) return;

  // Check cooldown — BUT don't block for auto-target (player can approach while cooling)
  const cooldown = activeUnit?.cooldowns?.[skill.skill_id] || 0;

  const skillMode = `skill_${skill.skill_id}`;

  // Self-targeting skills auto-queue immediately (unchanged)
  if (skill.targeting === 'self') {
    if (cooldown > 0) return;  // Self skills need to be off cooldown
    const msg = {
      type: 'action', action_type: 'skill',
      skill_id: skill.skill_id,
      target_x: activeUnit.position.x, target_y: activeUnit.position.y,
    };
    if (isControllingAlly) msg.unit_id = activeUnitId;
    onAction(msg);
    return;
  }

  // --- Phase 10G: Target-first skill casting ---
  if (selectedTargetId) {
    const targetUnit = players[selectedTargetId];
    if (targetUnit && targetUnit.is_alive) {
      // Validate targeting compatibility
      const isEnemy = targetUnit.team !== myTeam;
      const isAlly = targetUnit.team === myTeam;
      const validTarget =
        (skill.targeting === 'enemy_adjacent' && isEnemy) ||
        (skill.targeting === 'enemy_ranged' && isEnemy) ||
        (skill.targeting === 'ally_or_self' && (isAlly || selectedTargetId === effectiveUnitId));

      if (validTarget) {
        // Check if already in range
        const inRange = isInSkillRange(activeUnit, targetUnit, skill);

        if (inRange && cooldown === 0) {
          // In range + off cooldown → cast immediately
          const msg = {
            type: 'action', action_type: 'skill',
            skill_id: skill.skill_id,
            target_x: targetUnit.position.x, target_y: targetUnit.position.y,
          };
          if (isControllingAlly) msg.unit_id = activeUnitId;
          onAction(msg);
        } else {
          // Out of range OR on cooldown → set auto-target with skill
          const msg = {
            type: 'set_auto_target',
            target_id: selectedTargetId,
            skill_id: skill.skill_id,
          };
          if (isControllingAlly) msg.unit_id = activeUnitId;
          onAction(msg);
        }
        return;  // Don't enter targeting mode — we handled it
      }
    }
  }

  // --- No valid selected target → fall back to existing targeting mode ---
  if (cooldown > 0) return;  // Can't enter targeting mode if on cooldown
  if (actionMode === skillMode) {
    dispatch({ type: 'SET_ACTION_MODE', payload: null });
  } else {
    dispatch({ type: 'SET_ACTION_MODE', payload: skillMode });
  }
}, [isDead, queueFull, activeUnit, actionMode, dispatch, onAction,
    isControllingAlly, activeUnitId, selectedTargetId, players, myTeam, effectiveUnitId]);
```

#### `isInSkillRange()` Helper (Client-Side)

Add a utility function (can be in BottomBar.jsx or a shared utility):

```javascript
function isInSkillRange(caster, target, skillDef) {
  const dx = Math.abs(caster.position.x - target.position.x);
  const dy = Math.abs(caster.position.y - target.position.y);

  switch (skillDef.targeting) {
    case 'enemy_adjacent':
      // Chebyshev ≤ 1
      return Math.max(dx, dy) <= 1 && (dx + dy) > 0;
    case 'enemy_ranged': {
      // Euclidean distance
      const effectiveRange = skillDef.range > 0 ? skillDef.range : (caster.ranged_range || 5);
      const dist = Math.sqrt(dx * dx + dy * dy);
      return dist <= effectiveRange;
    }
    case 'ally_or_self': {
      // Chebyshev ≤ skill range
      return Math.max(dx, dy) <= (skillDef.range || 1);
    }
    default:
      return false;
  }
}
```

#### Keyboard Hotkeys (1-5)

The existing hotkey handler calls `handleSkillClick(skill)` — it should automatically get the new selected-target-aware behavior with no additional changes.

#### BottomBar Needs Access to New State

`BottomBar.jsx` will need access to `selectedTargetId`, `players`, `myTeam`, and `effectiveUnitId` from game state. These should be passed as props or accessed via context, consistent with how other state is accessed in the component.

**Estimated scope:** ~60 lines BottomBar.jsx, ~15 lines utility function

---

### Phase 10G-7 — Visual Feedback & HUD Updates
**Priority: MEDIUM — Important for player understanding**

**Files:** `client/src/components/HUD/HUD.jsx`, `client/src/canvas/ArenaRenderer.js`, `client/src/styles/main.css`

#### HUD Target Display — Skill Info

The existing auto-target HUD frame (Phase 10E-2) shows target name, HP bar, and "Pursuing..."/"Attacking!" status. Extend this:

When `autoSkillId` is set:
- Show the skill icon and name: `"⚔ Casting: Power Shot"`
- Status text changes:
  - **"Approaching..."** — out of range, moving closer
  - **"Cooling down (3)..."** — in range but skill on cooldown (show remaining turns)
  - **"Casting!"** — in range, skill being used
- For heals: tint the HUD frame green instead of red

```javascript
// In HUD auto-target section:
const statusText = autoSkillId
  ? (isInRange ? (isOnCooldown ? `Cooldown (${cdRemaining})` : `Casting ${skillName}!`) : `Approaching for ${skillName}...`)
  : (isAdjacent ? 'Attacking!' : 'Pursuing...');
```

#### Target Reticle Color

The existing pulsing bracket reticle (Phase 10E-1) is red for melee pursuit. Differentiate skill pursuit:

| Scenario | Reticle Color |
|----------|--------------|
| Melee auto-target (no skill) | Red (existing) |
| Offensive skill auto-target | Orange/amber |
| Heal/support skill auto-target | Green |

```javascript
// In drawTargetReticle():
const color = autoSkillId
  ? (skillDef.targeting === 'ally_or_self' ? '#44ff44' : '#ffaa00')
  : '#ff4444';
```

#### Selected Target Indicator (from 10G-5)

When a unit is soft-selected (before a skill is pressed), render a subtle indicator:
- Thin white/gold circle
- Non-pulsing (steady state)
- Shows the unit's name/HP in the HUD as a "Target Info" pane

This lets the player confirm they've selected the right target before pressing a skill key.

#### Combat Log

Extend combat log messages from Phase 10E-3:

```
"✨ Auto-casting Power Shot on: Skeleton Warrior"
"✨ Auto-casting Heal on: Party Crusader"
"⚔ Auto-targeting: Skeleton Warrior"  (existing — melee)
```

**Estimated scope:** ~30 lines HUD, ~15 lines renderer, ~10 lines CSS

---

### Phase 10G-8 — Edge Cases & Robustness
**Priority: MEDIUM — Prevents bugs**

**Files:** `server/app/core/match_manager.py`, `server/app/services/websocket.py`

#### Skill Becomes Unavailable Mid-Pursuit

If the player's skill becomes unusable while pursuing (e.g., class change — unlikely, but defensive):
- `generate_auto_target_action()` calls `can_use_skill()` each tick
- If it returns `(False, reason)` AND the skill is not just on cooldown → clear auto-target
- Cooldown is expected — keep pursuing. Other failures (class restriction, skill removed) → cancel

```python
can_use, reason = can_use_skill(player, auto_skill_id)
if not can_use:
    cd_remaining = player.cooldowns.get(auto_skill_id, 0)
    if cd_remaining > 0:
        pass  # Just on cooldown — keep approaching or waiting
    else:
        # Genuinely can't use this skill — cancel
        clear_auto_target(match_id, player_id)
        return None
```

#### Target Healed to Full (Heal-Specific)

When auto-casting Heal on an ally:
- If the target is already at full HP, the Heal skill still resolves (server-side, it heals 0)
- The auto-target should NOT clear — the player may want to keep healing as the ally takes damage
- No special handling needed; the server's skill resolution handles overheal gracefully

#### Switching Skills on Same Target

If the player has a target auto-targeted with Power Shot and then presses Double Strike:
- The new `set_auto_target` message replaces the previous one (same as switching melee targets)
- `auto_skill_id` updates to the new skill
- Existing behavior of `set_auto_target` clearing the queue handles this

#### Party Members — Controlled Allies

The skill auto-target should work for controlled party members:
- Player selects a target, switches to a party member, presses skill → `set_auto_target` with `unit_id` = party member
- The party member pursues and casts
- Already supported by the existing `unit_id` field in WS messages

#### Auto-Target Persists After Cast

After a successful skill cast, the skill goes on cooldown. The auto-target should persist:
1. Tick N: In range, off cooldown → SKILL action generated → cast happens
2. Tick N+1: In range, on cooldown → WAIT (stay positioned)
3. Tick N+5: In range, off cooldown → SKILL action generated again
4. Target flees → MOVE to chase, then repeat

This allows a Ranger to keep Power Shotting every 5 turns automatically.

#### Death Cleanup

When a player or their target dies, the existing death cleanup (Phase 10B-3) already clears `auto_target_id`. Since `clear_auto_target()` will also clear `auto_skill_id`, no additional logic is needed.

#### Tests

**New/extended in:** `server/tests/test_auto_target.py`

| Test | Description |
|------|-------------|
| `test_set_auto_target_with_skill` | Set auto-target with skill_id → both fields stored |
| `test_set_auto_target_skill_wrong_class` | Player can't use the skill → error |
| `test_set_auto_target_heal_on_enemy` | Heal skill on enemy → error (wrong targeting) |
| `test_set_auto_target_heal_on_ally` | Heal skill on ally → success (same team allowed) |
| `test_set_auto_target_offensive_on_ally` | Enemy-only skill on ally → error |
| `test_clear_auto_target_clears_skill` | Clearing auto-target also clears auto_skill_id |
| `test_generate_skill_action_in_range` | In skill range + off cooldown → SKILL action |
| `test_generate_skill_action_out_of_range` | Out of range → MOVE toward target |
| `test_generate_skill_action_cooldown_in_range` | In range + on cooldown → WAIT |
| `test_generate_skill_action_cooldown_out_of_range` | Out of range + on cooldown → MOVE |
| `test_generate_skill_action_los_blocked` | In range, no LOS → MOVE to reposition |
| `test_generate_skill_action_heal_ally` | Heal auto-target on ally → SKILL action when in range |
| `test_generate_skill_action_uses_ranged_range` | Power Shot range=0 → uses player's ranged_range |
| `test_generate_skill_action_persists_after_cast` | Skill cast → cooldown → auto-target persists → casts again |
| `test_generate_skill_melee_fallback` | No skill_id → existing melee ATTACK behavior unchanged |
| `test_skill_auto_target_death_cleanup` | Target dies → both auto_target_id and auto_skill_id cleared |

**Estimated scope:** ~30 lines edge cases, ~200 lines tests

---

## Sub-Phase Summary

| Phase | Name | Scope | Dependencies |
|-------|------|-------|--------------|
| **10G-1** | Server Model — `auto_skill_id` | PlayerState field + match_manager helper updates | Phase 10A–10F (completed) |
| **10G-1** | Server Model — `auto_skill_id` | ✅ COMPLETE | 10G-1 |
| **10G-2** | Server — Skill action generation | ✅ COMPLETE | 10G-1 |
| **10G-3** | WebSocket Protocol Extensions | ✅ COMPLETE | 10G-1 |
| **10G-4** | Client State — `selectedTargetId` + `autoSkillId` | ✅ COMPLETE | 10G-3 |
| **10G-5** | Client — Left-click target selection | ✅ COMPLETE | 10G-4 |
| **10G-6** | Client — Skill button with selected target | ✅ COMPLETE | 10G-4, 10G-5 |
| **10G-7** | Visual Feedback & HUD | ✅ COMPLETE | 10G-5, 10G-6 |
| **10G-8** | Edge Cases & Tests | ✅ COMPLETE | 10G-2 |

### Recommended Implementation Order

```
10G-1  →  10G-2  →  10G-3  →  10G-4  →  10G-5  →  10G-6  →  10G-7
                      ↓
                    10G-8 (can be done in parallel with 10G-5/10G-6/10G-7)
```

**10G-1 → 10G-2** is the critical path — once the server generates skill actions via auto-target, the feature works (testable via raw WS messages).

**10G-3 → 10G-4 → 10G-5 → 10G-6** wires it up to the client with the new "target-first" UX.

**10G-7** is polish.

**10G-8** hardens edge cases + adds test coverage.

---

## Estimated Total Scope

| Category | Lines |
|----------|-------|
| Server model + helpers | ~35 |
| Server action generation | ~100 |
| Server WS handlers | ~25 |
| Client state + messages | ~65 |
| Client target selection | ~45 |
| Client skill button logic | ~75 |
| Client visual feedback | ~55 |
| Tests | ~200 |
| Docs | ~10 |
| **Total** | **~610 lines** |

**Estimated sessions:** 2 focused sessions (10G-1 through 10G-3 in session 1, 10G-4 through 10G-8 in session 2).

---

## What This Does NOT Change

- **Turn resolver** — Skill resolution logic is untouched. Skills still resolve the same way in Phase 1.9. Auto-target just ensures the SKILL action has fresh coordinates and fires at the right time.
- **AI behavior** — Enemy AI and party AI continue using their existing stance/decision systems. Skill auto-target only applies to human-controlled units and controlled party members.
- **Skill config** — No changes to `skills_config.json`. All targeting types, ranges, and cooldowns remain as-is.
- **Existing skill targeting mode** — The click-to-highlight targeting mode still works as a fallback when no target is selected. Players who prefer the old flow can still use it.
- **Existing melee auto-target** — When no `skill_id` is provided, behavior is identical to Phase 10 (chase + melee attack).
- **`self` and `empty_tile` skills** — War Cry and Shadow Step are unaffected. They don't target units.

---

## Player-Facing UX Summary

### New Flow (Target-First)
1. **Left-click an enemy** → gold selection ring appears, HUD shows target info
2. **Press skill hotkey (1-5)** → if in range, cast immediately. If out of range, unit auto-paths to range and casts on arrival. "Approaching for Power Shot..." shown in HUD.
3. **Left-click a friendly unit** → same selection ring, but green
4. **Press Heal hotkey** → if in range, cast immediately. If out of range, auto-path and heal on arrival.
5. **Escape** at any time → cancels pursuit, clears selection

### Old Flow (Still Works)
1. **Press skill button** → enter targeting mode with tile highlights
2. **Left-click highlighted tile** → cast skill
3. Nothing changes for players who prefer this flow

### Both Flows Available Simultaneously
- If a target is selected AND you press a compatible skill → target-first flow
- If no target is selected AND you press a skill → existing targeting mode
- Players naturally discover the target-first flow as they play

---

## Implementation Log

### 10G-1: Server Model — `auto_skill_id` — DONE
- Added `auto_skill_id: str | None = None` field to `PlayerState` in [server/app/models/player.py](../../server/app/models/player.py) (line 65), directly below `auto_target_id`
- Updated `set_auto_target()` in [server/app/core/match_manager.py](../../server/app/core/match_manager.py) (line 664):
  - Added optional `skill_id` parameter
  - When `skill_id` is provided, validates: skill exists, player's class can use it, targeting type is compatible with target team relationship
  - `ally_or_self` skills (Heal) allow same-team targets — bypasses the "different team" check
  - `self` and `empty_tile` skills are rejected (they don't support auto-targeting)
  - Cooldown is NOT checked — player can approach while skill cools down
  - Stores `player.auto_skill_id = skill_id` alongside `player.auto_target_id = target_id`
- Updated `clear_auto_target()` (line 738): also clears `player.auto_skill_id = None`
- Updated `queue_action()` (line 580): also clears `player.auto_skill_id = None` when a new manual command overrides pursuit
- **~40 lines** of server model + helper changes

### 10G-2: Server — Extend `generate_auto_target_action()` for Skills — DONE
- Replaced the Phase 10B `generate_auto_target_action()` in [server/app/core/match_manager.py](../../server/app/core/match_manager.py) (line 758) with a skill-aware version
- Added two new helper functions:
  - `_get_skill_effective_range(skill_def, player)` — resolves effective range per targeting type (`enemy_adjacent` → 1, `enemy_ranged` with range=0 → `player.ranged_range`, etc.)
  - `_is_in_skill_range(player_pos, target_pos, effective_range, targeting_type)` — checks range using Chebyshev for adjacent/ally skills, Euclidean for ranged skills
- Extracted `_generate_move_toward()` helper to DRY up A*/door/move logic (reused by both skill and melee paths)
- Extended decision logic when `auto_skill_id` is set:
  1. **Team validation** adapts to skill targeting: `ally_or_self` → allows same team; offensive → requires different team
  2. **Skill usability check**: calls `can_use_skill()` each tick — if unusable due to class restriction (not cooldown), cancels auto-target
  3. **In range + off cooldown** → generates `ActionType.SKILL` with skill_id and target's live coordinates
  4. **In range + on cooldown** → generates `ActionType.WAIT` (hold position)
  5. **In range + LOS blocked** (for `requires_line_of_sight` skills like Power Shot) → generates MOVE to reposition
  6. **Out of range** (cooldown or not) → generates MOVE toward target via A*
- When `auto_skill_id` is NOT set, existing melee pursuit behavior is completely unchanged
- **~140 lines** of server action generation code
- Added **22 new tests** to [server/tests/test_auto_target.py](../../server/tests/test_auto_target.py):
  - `TestSetAutoTargetWithSkill` (9 tests): skill field storage, class validation, targeting compatibility, heal on ally/enemy, offensive on ally, self-skill rejection, unknown skill, clear clears both fields, queue clears both fields
  - `TestGenerateSkillAutoTargetAction` (13 tests): SKILL in range, MOVE out of range, WAIT on cooldown in range, MOVE on cooldown out of range, LOS blocked → MOVE, LOS clear → SKILL, heal ally in/out of range, ranged_range fallback for Power Shot, persists-after-cast cycle (SKILL → WAIT → SKILL), melee fallback (no skill), death cleanup, unreachable cleanup
- All **55 tests** pass (33 existing Phase 10A/10B + 22 new Phase 10G)

### 10G-3: WebSocket Protocol Extensions — DONE
- Updated `set_auto_target` WS handler in [server/app/services/websocket.py](../../server/app/services/websocket.py) (line 1137):
  - Reads optional `skill_id` from message data
  - Passes `skill_id` to `set_auto_target(match_id, unit_id, target_id, skill_id=skill_id)`
  - Includes `skill_id` and `skill_name` in `auto_target_set` response when a skill was specified
- Updated `turn_result` auto-targets sync (line 430):
  - Changed from `{ unit_id: target_id }` to `{ unit_id: { target_id, skill_id } }` object format
  - Both player and party member auto-targets include skill state
- Updated [docs/websocket-protocol.md](../../docs/websocket-protocol.md):
  - `set_auto_target` now documents optional `skill_id` field
  - `auto_target_set` response documents `skill_id` and `skill_name` fields
  - `turn_result.auto_targets` documents object format with `target_id` and `skill_id`
  - Version bumped to 7.0
- **~30 lines** server WS + docs changes

### 10G-4: Client State — `selectedTargetId` + `autoSkillId` — DONE
- Added new state fields to [client/src/context/GameStateContext.jsx](../../client/src/context/GameStateContext.jsx):
  - `autoSkillId: null` — skill being auto-cast alongside autoTargetId
  - `partyAutoSkills: {}` — `{ unitId: skillId }` for party members
  - `selectedTargetId: null` — unit soft-selected via left-click (client-only)
- Updated `TURN_RESULT` reducer to read new object format: `auto_targets[uid].target_id` and `auto_targets[uid].skill_id`
- Updated `AUTO_TARGET_SET` reducer to store `skill_id` and clear `selectedTargetId`
- Updated `AUTO_TARGET_CLEARED` and `CLEAR_AUTO_TARGET` to clear `autoSkillId` and `partyAutoSkills`
- Added `SELECT_TARGET` and `CLEAR_SELECTED_TARGET` reducer cases
- `SET_ACTION_MODE` clears `selectedTargetId` when entering a targeting mode
- Match start and Escape key both clear `selectedTargetId`
- Updated [client/src/App.jsx](../../client/src/App.jsx) `auto_target_set` handler:
  - Differentiates combat log for skill (`✨ Auto-casting Power Shot on: ...`) vs melee (`⚔ Auto-targeting: ...`)
- **~55 lines** client state changes

### 10G-5: Client — Left-Click Target Selection — DONE
- Updated `handleCanvasClick` in [client/src/components/Arena/Arena.jsx](../../client/src/components/Arena/Arena.jsx):
  - When no action mode is active and left-clicking a non-party, non-self unit → dispatches `SELECT_TARGET`
  - Clicking empty space → dispatches `CLEAR_SELECTED_TARGET`
  - Right-clicking an enemy also sets `selectedTargetId` (keeps in sync with auto-target)
  - Right-clicking non-attack (move/interact) clears `selectedTargetId`
- Added `drawSelectedTargetIndicator()` to [client/src/canvas/ArenaRenderer.js](../../client/src/canvas/ArenaRenderer.js):
  - Gold ring for enemies, green ring for allies — steady with very subtle pulse
  - Dashed outer ring for depth
  - Drawn before auto-target reticle; skipped if the unit is already auto-targeted
- Added `selectedTargetId` parameter to `renderFrame()` and passed from Arena.jsx
- **~50 lines** Arena.jsx + ArenaRenderer.js changes

### 10G-6: Client — Skill Button with Selected Target — DONE
- Added `isInSkillRange()` utility function to [client/src/components/BottomBar/BottomBar.jsx](../../client/src/components/BottomBar/BottomBar.jsx):
  - Mirrors server-side `_is_in_skill_range()` logic
  - Chebyshev for adjacent/ally skills, Euclidean for ranged skills
- Rewrote `handleSkillClick()` with target-first flow:
  1. Self-targeting skills unchanged (auto-queue immediately)
  2. If `selectedTargetId` is set and compatible with skill targeting type:
     - In range + off cooldown → cast immediately (send `action` message)
     - Out of range or on cooldown → send `set_auto_target` with `skill_id` (auto-path + auto-cast)
  3. No valid selected target → fall back to existing targeting mode toggle
- Updated skill button disabled logic: skills on cooldown are clickable when a target is selected (enables auto-target approach while cooling)
- BottomBar now reads `selectedTargetId` from game state
- **~80 lines** BottomBar.jsx changes

### 10G-7: Visual Feedback & HUD Updates — DONE
- Updated [client/src/components/HUD/HUD.jsx](../../client/src/components/HUD/HUD.jsx):
  - Added `isInSkillRange()` helper (mirrors BottomBar) for computing real-time skill range status
  - Reads `autoSkillId`, `selectedTargetId`, `classSkills`, `allClassSkills` from game state
  - Resolves `autoSkillDef` from available skill data for icon/name/targeting info
  - **Skill-aware auto-target status text**:
    - `"Approaching for Power Shot..."` — out of range, moving closer
    - `"Cooldown (3)"` — in range but on cooldown (shows remaining turns)
    - `"Casting Power Shot!"` — in range, off cooldown, skill being used
  - **Heal variant**: When `autoSkillDef.targeting === 'ally_or_self'`, applies `.auto-target-heal` class — green-tinted frame, green HP bar, green icon/text
  - **Skill icon + name in header**: Shows skill icon and `"Skill: Power Shot"` instead of generic `"Targeting:"`
  - **Selected target info pane**: New `.hud-selected-target` section shown when a unit is soft-selected (before auto-target). Displays target name, HP bar, with gold styling for enemies and green for allies
  - Pane hides when auto-target is active (replaced by auto-target frame)
- Updated [client/src/canvas/ArenaRenderer.js](../../client/src/canvas/ArenaRenderer.js):
  - Modified `drawTargetReticle()` to accept optional `color` parameter (`{ r, g, b }` object)
  - Reticle brackets and glow ring now dynamically colored:
    - **Melee pursuit (no skill)**: Red `(255, 60, 60)` — unchanged default
    - **Offensive skill pursuit**: Orange/amber `(255, 170, 0)`
    - **Heal/support skill pursuit**: Green `(68, 255, 68)`
  - Added `_findSkillDef()` helper to look up skill definitions from `classSkills`/`allClassSkills`
  - `renderFrame()` now accepts `autoSkillId`, `partyAutoSkills`, `allClassSkills`, `classSkills` params
  - Reticle rendering loop builds `autoTargetSkillMap` to associate each target with its skill, resolves skill definition per-target to determine color
- Updated [client/src/components/Arena/Arena.jsx](../../client/src/components/Arena/Arena.jsx):
  - Destructures `autoSkillId`, `partyAutoSkills` from game state
  - Passes `autoSkillId`, `partyAutoSkills`, `allClassSkills`, `classSkills` to `renderFrame()`
  - Added to render effect dependency array
- Updated [client/src/styles/main.css](../../client/src/styles/main.css):
  - `.status-casting` — orange pulsing text for active skill casting
  - `.status-cooldown` — muted purple text for cooldown waiting
  - `.auto-target-heal` — green-tinted variant of auto-target frame (background, border, icon, label, name, HP text colors)
  - `.hp-fill-heal` — green HP bar gradient for heal targets
  - `.hud-selected-target` — selected target info pane with enemy (gold) and ally (green) variants
  - HP bar, name, label, and text styles for both enemy and ally selected targets
- **All 55 server tests pass**, client builds cleanly
- **~55 lines** HUD + ~35 lines renderer + ~10 lines Arena.jsx + ~120 lines CSS

### 10G-8: Edge Cases & Robustness — DONE
- **Audited all 10G-8 edge cases** listed in spec — server code in [server/app/core/match_manager.py](../../server/app/core/match_manager.py) already handled them correctly during 10G-2 implementation:
  - **Skill unavailable mid-pursuit**: `generate_auto_target_action()` calls `can_use_skill()` each tick; non-cooldown failures cancel auto-target (lines 893–903)
  - **Switching skills on same target**: `set_auto_target()` overwrites `auto_skill_id` cleanly (line 734)
  - **Death cleanup**: `clear_auto_target()` clears both `auto_target_id` and `auto_skill_id` (lines 738–744)
  - **queue_action clears skill**: Both fields cleared when manual command overrides pursuit (lines 604–605)
  - **Target healed to full (Heal)**: No special handling needed — server overheal is graceful
  - **Party member skill pursuit**: Supported via `unit_id` field — no additional logic needed
  - **Auto-target persists after cast**: Cooldown cycle (SKILL → WAIT → SKILL) works correctly
- **Added 11 new dedicated edge case tests** in `TestSkillAutoTargetEdgeCases` class in [server/tests/test_auto_target.py](../../server/tests/test_auto_target.py):
  - `test_switch_skill_on_same_target` — verifies skill overwrite, invalid skill doesn't clobber existing
  - `test_switch_from_melee_to_skill_on_same_target` — melee → skill transition
  - `test_switch_from_skill_to_melee_on_same_target` — skill → melee transition
  - `test_skill_unavailable_mid_pursuit_class_restriction` — class change mid-pursuit cancels auto-target
  - `test_skill_on_cooldown_mid_pursuit_keeps_going` — cooldown is NOT a cancel reason
  - `test_heal_on_full_hp_target_persists` — overheal is graceful, auto-target persists
  - `test_party_member_skill_auto_target` — controlled Crusader uses Double Strike pursuit
  - `test_party_member_heal_skill_auto_target` — controlled Confessor heals player via pursuit
  - `test_skill_auto_target_multi_cycle_persistence` — full cast → cooldown → chase → cast lifecycle
  - `test_offensive_skill_target_becomes_ally` — team change cancels offensive pursuit
  - `test_heal_target_becomes_enemy` — team change cancels heal pursuit
- **All 66 tests pass** (33 Phase 10A/10B + 22 Phase 10G core + 11 Phase 10G-8 edge cases)
- **~200 lines** of new test code
