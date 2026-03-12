# WebSocket Protocol — Arena Prototype

This document defines all WebSocket message types exchanged between the client and server.

**Endpoint:** `ws://<host>/ws/{match_id}/{player_id}`

---

## Client → Server Messages

### Submit Action
Queue an action for the current turn.
```json
{
  "type": "action",
  "action_type": "move | attack | wait",
  "target_x": 5,
  "target_y": 3
}
```
- `target_x`/`target_y` required for `move` and `attack`, ignored for `wait`.
- Only the **last** action submitted before the tick fires is used.

### Player Ready
Signal ready status in the lobby.
```json
{
  "type": "ready"
}
```

---

## Server → Client Messages

### Action Queued (ACK)
Confirms the server received and queued the player's action.
```json
{
  "type": "action_queued",
  "action_type": "move"
}
```

### Player Ready Broadcast
Sent to all players when someone readies up.
```json
{
  "type": "player_ready",
  "player_id": "abc123"
}
```

### Player Joined
Sent to all players when a new player joins the match.
```json
{
  "type": "player_joined",
  "player_id": "abc123",
  "username": "Alice",
  "position": { "x": 1, "y": 1 }
}
```

### Match Start
Sent when all players are ready and the match begins.
```json
{
  "type": "match_start",
  "match_id": "a1b2c3d4",
  "players": {
    "abc123": { "username": "Alice", "position": { "x": 1, "y": 1 }, "hp": 100, "max_hp": 100 },
    "def456": { "username": "Bob", "position": { "x": 13, "y": 1 }, "hp": 100, "max_hp": 100 }
  },
  "grid_width": 15,
  "grid_height": 15,
  "obstacles": [{ "x": 7, "y": 7 }, { "x": 6, "y": 7 }],
  "tick_rate": 10
}
```

### Turn Result
Broadcast every tick with the results of all resolved actions.
```json
{
  "type": "turn_result",
  "match_id": "a1b2c3d4",
  "turn_number": 42,
  "actions": [
    {
      "player_id": "abc123",
      "username": "Alice",
      "action_type": "attack",
      "success": true,
      "message": "Alice hit Bob for 15 damage",
      "target_id": "def456",
      "target_username": "Bob",
      "damage_dealt": 15,
      "target_hp_remaining": 85,
      "killed": false
    },
    {
      "player_id": "def456",
      "username": "Bob",
      "action_type": "move",
      "success": true,
      "message": "Bob moved to (6, 3)",
      "from_x": 5,
      "from_y": 3,
      "to_x": 6,
      "to_y": 3
    }
  ],
  "deaths": [],
  "winner": null,
  "players": {
    "abc123": { "position": { "x": 5, "y": 5 }, "hp": 100, "is_alive": true },
    "def456": { "position": { "x": 6, "y": 3 }, "hp": 85, "is_alive": true }
  }
}
```

### Match End
Broadcast when a winner is determined or match timer expires.
```json
{
  "type": "match_end",
  "match_id": "a1b2c3d4",
  "winner": "abc123",
  "winner_username": "Alice",
  "final_turn": 42,
  "stats": {
    "abc123": { "username": "Alice", "kills": 1, "damage_dealt": 100 },
    "def456": { "username": "Bob", "kills": 0, "damage_dealt": 45 }
  }
}
```

### Player Disconnected
Sent when a player's WebSocket connection drops.
```json
{
  "type": "player_disconnected",
  "player_id": "def456"
}
```

### Error
Sent for invalid actions or server-side issues.
```json
{
  "type": "error",
  "message": "Invalid action: target out of range"
}
```

### Team Changed (Phase 2)
Sent to all lobby members when a player changes teams.
```json
{
  "type": "team_changed",
  "player_id": "abc123",
  "username": "Alice",
  "team": "b",
  "players": { ... }
}
```

### Chat Message (Phase 2.1 — Chunk 3)
Sent to all lobby members when someone sends a chat message.
```json
{
  "type": "chat_message",
  "sender": "Alice",
  "sender_id": "abc123",
  "message": "Ready when you are!",
  "timestamp": 1739404800.0
}
```

### Config Changed (Phase 2.1 — Chunk 3)
Sent to all lobby members when host updates match config.
```json
{
  "type": "config_changed",
  "config": {
    "map_id": "maze",
    "match_type": "mixed",
    "ai_opponents": 3,
    "ai_allies": 1,
    "max_players": 8
  },
  "players": { ... }
}
```

---

## Client → Server Messages (Phase 2.1 — Chunk 3)

### Team Select
Switch teams in lobby.
```json
{
  "type": "team_select",
  "team": "b"
}
```

### Lobby Chat
Send a chat message in lobby.
```json
{
  "type": "lobby_chat",
  "message": "Hello everyone!"
}
```

### Lobby Config (Host Only)
Update match configuration in lobby.
```json
{
  "type": "lobby_config",
  "config": {
    "map_id": "maze",
    "match_type": "mixed",
    "ai_opponents": 3,
    "ai_allies": 1
  }
}
```

### Class Select (Phase 4A)
Select a class in the lobby before match start.
```json
{
  "type": "class_select",
  "class_id": "ranger"
}
```
**Valid `class_id` values:** `"crusader"`, `"confessor"`, `"inquisitor"`, `"ranger"`, `"hexblade"`

---

## Server → Client Messages (Phase 4A)

### Class Changed
Broadcast to all lobby players when someone selects a class.
```json
{
  "type": "class_changed",
  "player_id": "abc123",
  "username": "Player1",
  "class_id": "ranger",
  "players": {
    "abc123": {
      "username": "Player1",
      "team": "a",
      "ready": false,
      "class_id": "ranger"
    }
  }
}
```

---

## Phase 7B-1: Multi-Control & Group Commands

### Select All Party Members
Select all alive hero allies for simultaneous control.
```json
{
  "type": "select_all_party"
}
```
**Response:**
```json
{
  "type": "all_party_selected",
  "selected_ids": ["ally1", "ally2", "ally3"],
  "party": [ ... party member objects ... ]
}
```

### Release All Party Members
Release all units controlled by this player back to AI autonomy.
```json
{
  "type": "release_all_party"
}
```
**Response:**
```json
{
  "type": "all_party_released",
  "released_ids": ["ally1", "ally2", "ally3"],
  "party": [ ... party member objects ... ]
}
```

### Group Action
Queue the same action for all controlled units (+ player). Optionally specify `unit_ids` to target specific units.
```json
{
  "type": "group_action",
  "action_type": "move",
  "target_x": 5,
  "target_y": 3,
  "unit_ids": ["ally1", "ally2"]
}
```
**Response:**
```json
{
  "type": "group_action_queued",
  "queued": ["ally1", "ally2"],
  "failed": [],
  "queues": { "ally1": [...], "ally2": [...] }
}
```

### Group Batch Actions
Queue per-unit smart-click paths for multiple units at once. Clears existing queues (replace mode).
```json
{
  "type": "group_batch_actions",
  "unit_actions": [
    {
      "unit_id": "ally1",
      "actions": [
        { "action_type": "move", "target_x": 2, "target_y": 3 },
        { "action_type": "move", "target_x": 2, "target_y": 4 }
      ]
    },
    {
      "unit_id": "ally2",
      "actions": [
        { "action_type": "move", "target_x": 3, "target_y": 3 }
      ]
    }
  ]
}
```
**Response:**
```json
{
  "type": "group_batch_queued",
  "queued": [{"unit_id": "ally1", "count": 2}, {"unit_id": "ally2", "count": 1}],
  "failed": [],
  "queues": { "ally1": [...], "ally2": [...] }
}
```

### Set Stance
Set the AI behavior stance for a single hero ally unit.
```json
{
  "type": "set_stance",
  "unit_id": "ally1",
  "stance": "aggressive"
}
```
Valid stances: `"follow"` (default), `"aggressive"`, `"defensive"`, `"hold"`

**Response:**
```json
{
  "type": "stance_updated",
  "unit_id": "ally1",
  "stance": "aggressive",
  "party": [{ "unit_id": "ally1", "username": "Hero1", "class_id": "crusader", "hp": 100, "max_hp": 100, "is_alive": true, "hero_id": "h1", "controlled_by": null, "position": {"x": 3, "y": 3}, "ai_stance": "aggressive" }]
}
```

### Set All Stances
Set the AI behavior stance for ALL alive hero allies owned by the player.
```json
{
  "type": "set_all_stances",
  "stance": "defensive"
}
```
**Response:**
```json
{
  "type": "all_stances_updated",
  "stance": "defensive",
  "updated_ids": ["ally1", "ally2"],
  "party": [...]
}
```

---

## Message Flow Diagram

```
  CLIENT                           SERVER
    │                                │
    │──── { type: "ready" } ────────►│
    │                                │──── broadcast player_ready
    │◄─── { type: "player_ready" } ──│
    │                                │
    │──── { type: "lobby_chat" } ───►│
    │◄─── { type: "chat_message" } ─│  (broadcast to all)
    │                                │
    │──── { type: "lobby_config" } ─►│  (host only)
    │◄─── { type: "config_changed" }│  (broadcast to all)
    │                                │
    │──── { type: "team_select" } ──►│
    │◄─── { type: "team_changed" } ─│  (broadcast to all)
    │                                │
    │──── { type: "class_select" } ─►│
    │◄─── { type: "class_changed" } │  (broadcast to all)
    │                                │
    │   (all humans ready)           │
    │◄─── { type: "match_start" } ──│
    │                                │
    │──── { type: "action", ... } ──►│  (queued)
    │◄─── { type: "action_queued" }─│
    │                                │
    │          ⏱️ TICK fires          │
    │                                │──── resolve all actions
    │◄─── { type: "turn_result" } ──│
    │                                │
    │     ... repeat each tick ...   │
    │                                │
    │◄─── { type: "match_end" } ────│
```

---

## Phase 10C: Auto-Target & Melee Pursuit

### Client → Server

#### Set Auto-Target
Right-click an enemy to persistently chase and melee attack them, or press a skill button with a selected target to auto-path and cast. The server generates chase/attack/skill actions each tick until the target dies, becomes unreachable, or the player issues a new command.
```json
{
  "type": "set_auto_target",
  "target_id": "enemy_abc123",
  "unit_id": "player_id_or_party_member_id",
  "skill_id": "power_shot"
}
```
- `target_id` — the enemy unit's player_id to pursue (or ally for heal-type skills)
- `unit_id` — optional, defaults to sender. Use a party member's unit_id to set their auto-target.
- `skill_id` — optional (Phase 10G). When provided, the server auto-casts this skill instead of melee attacking when in range. Omit for melee pursuit.

#### Clear Auto-Target
Explicitly cancel auto-target pursuit for a unit.
```json
{
  "type": "clear_auto_target",
  "unit_id": "player_id_or_party_member_id"
}
```

### Server → Client

#### Auto-Target Set (ACK)
Confirms the auto-target was successfully set.
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
- `skill_id` and `skill_name` — only present when a skill was specified (Phase 10G). Absent for melee pursuit.

#### Auto-Target Cleared
Sent when auto-target is cleared — either by player request or automatically by the server.
```json
{
  "type": "auto_target_cleared",
  "unit_id": "player_id",
  "reason": "target_died | unreachable | cancelled | new_command"
}
```
Reasons:
- `target_died` — the target was killed
- `unreachable` — A* pathfinding found no valid path to the target
- `cancelled` — player explicitly sent `clear_auto_target`
- `new_command` — player issued a new action that overrides pursuit

#### Turn Result — Auto-Targets Field
The `turn_result` payload includes an `auto_targets` field when any controlled unit has an active auto-target:
```json
{
  "type": "turn_result",
  "...": "...",
  "auto_targets": {
    "player_id": { "target_id": "enemy_abc123", "skill_id": "power_shot" },
    "party_member_id": { "target_id": "enemy_def456", "skill_id": null }
  }
}
```
- Each entry is an object with `target_id` and `skill_id` (null for melee pursuit).
- Absent entries mean no active auto-target for that unit.

---

## Floor Advance (Phase 12D)

When all enemies on a dungeon floor are defeated and a player interacts with the stairs tile, the server generates the next floor and broadcasts the new state.

### Client → Server

#### Interact — Enter Stairs
Sent when a player presses E while standing on an unlocked stairs tile.
```json
{
  "type": "action",
  "action_type": "interact",
  "target_id": "enter_stairs"
}
```
- Only valid when `stairs_unlocked` is `true` (all enemies dead).
- Player must be standing on a stairs (`T`) tile.
- Triggers a full floor transition for the **entire party**.

### Server → Client

#### Floor Advance Broadcast
Sent to all players in the match when the party descends to a new floor. Contains the complete new floor state.
```json
{
  "type": "floor_advance",
  "new_floor_number": 2,
  "grid_width": 24,
  "grid_height": 24,
  "tiles": [["W","W",".",...], ...],
  "tile_legend": { "W": "wall", ".": "floor", "D": "door", "T": "stairs", ... },
  "obstacles": [[1,1,1,0,...], ...],
  "door_states": { "5,10": false, "12,7": false },
  "chest_states": { "8,3": "closed", "15,12": "closed" },
  "players_snapshot": { ... },
  "visible_tiles": [[3,4],[3,5],[4,4], ...],
  "stairs_unlocked": false,
  "current_floor": 2
}
```
- `tiles` — full 2D tile grid for the new floor
- `tile_legend` — character → type mapping (same format as `match_start`)
- `obstacles` — binary obstacle grid for pathfinding
- `door_states` — all doors start closed on new floors
- `chest_states` — all chests start closed on new floors
- `players_snapshot` — updated entity positions/HP/state on the new floor
- `visible_tiles` — FOV-computed visible tiles from new spawn positions
- `stairs_unlocked` — always `false` on a new floor (must clear enemies again)
- `current_floor` — the new floor number

#### Turn Result — Stairs Fields
Each `turn_result` payload includes stairs and floor state:
```json
{
  "type": "turn_result",
  "...": "...",
  "stairs_unlocked": true,
  "current_floor": 1
}
```
- `stairs_unlocked` — updated each tick; `true` when all enemies are dead
- `current_floor` — current floor number for HUD display

---

**Version:** 8.0  
**Last Updated:** February 23, 2026  
**Phase 7B-1:** Added `select_all_party`, `release_all_party`, `group_action`, `group_batch_actions` messages for multi-unit control  
**Phase 7C-2:** Added `set_stance`, `set_all_stances` messages and `stance_updated`, `all_stances_updated` responses for AI behavior stances  
**Phase 10C:** Added `set_auto_target`, `clear_auto_target` messages and `auto_target_set`, `auto_target_cleared` responses for persistent melee pursuit  
**Phase 10G:** Extended `set_auto_target` and `auto_target_set` with optional `skill_id` for skill auto-casting. Extended `turn_result.auto_targets` to include skill state.  
**Phase 12D:** Added `floor_advance` broadcast message for multi-floor dungeon progression. Extended `turn_result` with `stairs_unlocked` and `current_floor` fields.
