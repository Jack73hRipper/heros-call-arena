# Party Control System — Implementation Document

## Overview

This document describes the **Party Control System** enhancement, which allows players to take direct control of allied AI party members during gameplay. Previously, AI allies operated fully autonomously with no player input. Now players can click on any ally to issue commands (move, attack, ranged attack, etc.) as if they were that unit.

---

## Changes Summary

### Problem Statement
1. **AI allies paced randomly** when no enemies were in range, making them appear restless and hard to position
2. **No player control over allies** — once spawned, hero allies were fully autonomous with zero player input
3. **Players wanted tactical control** — ability to position allies, coordinate attacks, and manage the party RPG-style

### Solution: 3-Tier Behavior Model
- **No control (default)**: AI ally fights enemies normally (aggressive/ranged behavior) but holds position instead of patrolling when idle
- **Controlled with queued actions**: Player has taken control and queued actions — AI skips this unit during its decision phase
- **Controlled but no actions queued**: AI resumes normal combat behavior (attack nearby enemies) while the unit remains "selected" for the player

---

## Files Modified

### Server-Side

#### 1. `server/app/models/player.py`
- **Added**: `controlled_by: str | None = None` field to `PlayerState`
- Tracks which player (if any) is currently controlling this AI unit

#### 2. `server/app/core/ai_behavior.py`
- **Removed patrol for hero allies**: In both `_decide_aggressive_action()` and `_decide_ranged_action()`, hero allies (units with `hero_id != None`) now return `WAIT` instead of executing patrol behavior when no enemies are in range
- **Added `controlled_ids` parameter** to `run_ai_decisions()`: AI decision loop skips units whose IDs are in the controlled set (these units have player-queued actions instead)

#### 3. `server/app/core/match_manager.py`
Added 5 new party management functions:
- **`is_party_member(match_id, player_id, unit_id)`** — Validates that a unit is a controllable ally for the given player. Checks hero ally ownership via `_hero_ally_map` and generic same-team AI allies.
- **`set_party_control(match_id, player_id, unit_id)`** — Sets `controlled_by` on the unit, releases any previous control by the same player
- **`release_party_control(match_id, player_id, unit_id)`** — Clears `controlled_by` on the unit
- **`get_controlled_unit_ids(match_id)`** — Returns set of AI unit IDs that are currently controlled AND have queued actions (used to skip AI decisions for these units)
- **`get_party_members(match_id, player_id)`** — Returns list of controllable ally dicts (unit_id, class_id, hero_id, controlled_by) for the party panel

#### 4. `server/app/services/websocket.py`
- **Updated imports** for new match_manager functions
- **`action` handler**: Reads `unit_id` from message, validates via `is_party_member()`, queues action under the unit's ID instead of player's
- **`batch_actions` handler**: Same unit_id routing for batch action replacement
- **`clear_queue` / `remove_last` handlers**: Support `unit_id` field for party member queue operations
- **Added `select_party_member` handler**: Calls `set_party_control()`, returns party state and unit's current queue
- **Added `release_party_member` handler**: Calls `release_party_control()`
- **Updated tick callback**: Passes `controlled_ids=get_controlled_unit_ids(match_id)` to `run_ai_decisions()`
- **Updated post-turn broadcast**: Includes `party` array from `get_party_members()` in queue update messages

### Client-Side

#### 5. `client/src/context/GameStateContext.jsx`
Added to state:
- `activeUnitId: null` — Currently controlled unit (null = player's own unit)
- `partyMembers: []` — List of controllable allies
- `partyQueues: {}` — Map of unit_id → action queue for party members

New/updated reducer cases:
- **`QUEUE_UPDATED`**: Routes queue updates to `partyQueues[unitId]` when `unit_id` is present and differs from player; stores `party` array
- **`QUEUE_CLEARED`**: Supports `unit_id` for party member queue clearing
- **`SELECT_ACTIVE_UNIT`**: Sets/clears `activeUnitId` and resets action mode
- **`PARTY_MEMBER_SELECTED`**: Updates active unit, party members list, and party queues
- **`PARTY_MEMBER_RELEASED`**: Clears `activeUnitId` if released unit was the active one
- **`MATCH_START` / `LEAVE_MATCH`**: Reset party state

#### 6. `client/src/App.jsx`
- Updated `action_queued` / `queue_updated` handlers to pass `unit_id` and `party` through to reducer
- Updated `queue_cleared` to pass `unit_id`
- Added `party_member_selected` and `party_member_released` message handlers

#### 7. `client/src/components/PartyPanel/PartyPanel.jsx` *(NEW)*
New component displaying:
- List of controllable party members with HP bars
- Click-to-select/deselect control
- Visual indicators for controlled units (CTRL badge, queue count)
- "↩ Self" button to quickly return to player's own character
- Disabled state for dead allies

#### 8. `client/src/components/ActionBar/ActionBar.jsx`
- Uses `activeUnitId || playerId` as the "effective unit" for computing state (HP, cooldowns, alive status)
- Shows correct queue (`partyQueues[activeUnitId]` vs player's `actionQueue`)
- All action messages include `unit_id` when controlling an ally
- Displays "Controlling [Ally Name]" label when active

#### 9. `client/src/components/Arena/Arena.jsx`
- **Click-to-select**: Left-clicking an allied unit with no action mode toggles party control
- **Highlights computed from active unit's position** (move, attack, ranged highlights all center on the controlled unit)
- **Viewport centers on active unit** in dungeon mode
- **Queue preview** shows the active unit's queue path
- **Right-click pathfinding** originates from active unit's position
- **All actions include `unit_id`** when controlling an ally
- **PartyPanel** added to sidebar (above ActionBar)

#### 10. `client/src/canvas/ArenaRenderer.js`
- **Accepts `activeUnitId` parameter** in `renderFrame()`
- **Draws pulsing cyan glow ring** around the controlled/active unit
- Inner dotted white ring for additional visibility

#### 11. `client/src/styles/main.css`
- Complete CSS for `.party-panel`, `.party-member`, HP bars, status indicators
- Styles for selected state (cyan glow border), dead state (dimmed), control badge
- "Controlling [name]" label style in ActionBar

---

## How It Works

### Player Workflow
1. **Start a match** with AI allies (dungeon with heroes, or arena with AI allies)
2. **Party Panel appears** in the sidebar showing all controllable allies
3. **Click an ally** (in the panel OR on the canvas) to take control
4. **Issue commands** — Move, Attack, Ranged, Wait, etc. — just like controlling your own character
5. **Right-click pathfinding** works from the ally's position
6. **Click "↩ Self"** or click the ally again to return to your character
7. **When not controlled**, allies fight enemies normally but hold position when idle (no random pacing)

### Server Logic Flow
```
Player sends: { type: "select_party_member", unit_id: "ai-1" }
  → Server validates ownership (is_party_member)
  → Sets unit.controlled_by = player_id
  → Returns party state + unit's queue

Player sends: { type: "action", action_type: "move", target_x: 5, target_y: 3, unit_id: "ai-1" }
  → Server validates unit_id is a party member
  → Creates PlayerAction with player_id = "ai-1"
  → Queues under "ai-1" (not under the player's queue)

On tick:
  → get_controlled_unit_ids() returns {"ai-1"} (has queued actions)
  → run_ai_decisions(controlled_ids={"ai-1"}) skips ai-1
  → ai-1 executes the player's queued move action
  → Other AI allies still make their own decisions normally
```

### Key Design Decision: Hybrid AI Control
The `get_controlled_unit_ids()` function only returns unit IDs that are controlled **AND** have queued actions. This means:
- If a player selects an ally but doesn't queue any actions, the AI still decides for that unit (attack nearby enemies, etc.)
- Only when the player explicitly queues actions does the AI step aside
- This gives a "hands-off when idle, hands-on when needed" experience

---

## Test Results

- **691 tests passing** (0 failures, 0 errors)
- Frontend builds cleanly (51 modules, 0 warnings)
- No lint/type errors in modified files

---

## Additional Ideas & Future Enhancements

### Formation System
- **Formation presets**: Line, wedge, defensive circle, spread — player clicks a formation button and allies auto-arrange
- **Formation drag**: Click and drag to set a formation shape, allies path to their assigned positions
- **Smart re-formation**: After combat, allies return to their formation positions relative to the player

### AI Behavior Stances
- **Aggressive**: Current default — pursue and attack enemies in vision range
- **Defensive**: Hold position, only attack enemies that come within 2 tiles
- **Follow**: Stay within 3 tiles of the player at all times, auto-reposition
- **Guard Point**: Hold a specific tile, attack enemies that come near
- UI: Right-click a party member for a stance dropdown

### Tactical Commands (Quick Orders)
- **"All Attack"**: All party members focus the clicked target
- **"All Hold"**: All party members stop and hold position
- **"All Follow"**: All party members regroup to the player
- **"Retreat"**: All party members path toward the dungeon entrance
- Keyboard shortcuts (F1-F4 for individual ally selection, F5 for all)

### Advanced Party Features
- **Ally inventory management**: View and manage ally equipment
- **Shared resource pool**: Distribute potions, scrolls between party members
- **Party buff coordination**: Show ability ranges/cooldowns for ally skills
- **Ally death consequences**: Morale system — other allies fight worse when an ally falls
- **Resurrection**: If a healer class ally is alive, allow reviving dead allies (limited uses)

### Visual Enhancements
- **Control tether line**: Draw a faint line from the player to the controlled unit
- **Party member portraits**: Show sprite/class icon in the PartyPanel instead of just text
- **Group health overview**: Overlay showing all party HP bars near the minimap
- **Command echo**: Brief floating text above the ally when given an order ("Moving!", "Attacking!")
- **Selection animation**: Particle effect on ally when selected/deselected

### Quality of Life
- **Tab-cycle through party members**: Press Tab to cycle control between allies
- **Shift-click multi-select**: Queue orders for multiple allies at once
- **Copy queue**: Copy the player's action queue to an ally
- **Auto-follow toggle**: Click-to-toggle an ally following the player at a set distance
- **Ally pathfinding preview**: When hovering with an ally selected, show the pathfinding preview in a different color
- **Quick swap hotkeys**: Number keys 1-4 to instantly switch between party members

### Persistence & Progression
- **Ally experience sharing**: Allies gain XP proportional to their contribution
- **AI behavior memory**: Allies "learn" from player commands (e.g., if often told to stay back, AI defaults to defensive)
- **Preferred formations**: Save formation preferences per hero roster
- **Party composition bonuses**: Synergy bonuses for specific class combinations (e.g., Crusader + Confessor = +10% party healing)

---

## Architecture Notes

The system is designed to be minimally invasive:
- Only 1 new field added to the data model (`controlled_by`)
- AI behavior changes are additive (2 early-return checks + 1 skip filter)
- WebSocket messages are backward-compatible (old clients ignore `unit_id` and `party` fields)
- State management follows the existing reducer pattern with no new contexts or providers
- The PartyPanel only renders when `partyMembers.length > 0`, so it's invisible in solo/no-ally matches
