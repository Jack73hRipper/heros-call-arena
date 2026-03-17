# Match Lobby Redesign — Implementation Plan

**Date:** March 14, 2026  
**Status:** Planning  
**Goal:** Replace the current dual-button (Enter Arena / Enter Dungeon) flow and cluttered War Room with a streamlined single-entry lobby where players assemble parties from their hero roster.

---

## 1. Design Overview

### What Changes

| Aspect | Current System | New System |
|--------|---------------|------------|
| Entry point | Two buttons: "Enter Arena" (PvP) + "Enter Dungeon" (requires pre-selecting heroes) | Single **"Create Match"** button — no pre-selection |
| Modes | 5 modes (pvp, solo_pve, mixed, dungeon, pvpve) — overlapping and confusing | **3 tabs: PvP · PvE · PvPvE** |
| Maps | 15 maps — most unused, confusing | **4 maps** scoped to their mode tab |
| Hero selection | Pick 4 heroes before lobby (dungeon only), then pick a *separate class* in lobby (arena) | Pick 1–5 heroes from your roster **inside the lobby**, designate which one you control |
| Class identity | Chosen separately from heroes (redundant) | Your class **is** the class of your controlled hero — no separate class picker |
| Party size | Max 4 heroes, max 5 dungeon party | **Max 5 heroes** per player, no minimum enforced |
| Multi-human teams | Not well supported | Humans on the same team each bring heroes from their own roster; coordinate to fill up to 5 team slots |
| AI opponent config | Generic AI with class dropdowns | Stays for non-roster AI teams; PVPVE gets rich team/density controls |

### What Stays the Same
- Notice Board (browse & join matches) — hooks into new lobby
- Chat in lobby
- Team selection (A/B/C/D)
- Ready / Start match flow
- All backend match lifecycle (match_manager, hero_manager, turn resolver)
- Post-match flow, permadeath, loot persistence

---

## 2. Mode Tabs & Map Assignments

### PvP Tab
- **Map:** Arena Classic (fixed — no map dropdown needed)
- **Description:** Team vs Team combat. No PvE monsters. Pure player skill.
- **Config controls:** Team assignment only (A vs B, or free-for-all)
- **Hero selection:** Each player picks 1–5 heroes from their roster, designates their controlled hero. Remaining heroes become AI allies on their team.

### PvE Tab
- **Maps:** Wave Arena · Training Room · The Crypt
- **Map dropdown** to select between the three
- **Description:** Cooperative — fight waves/dungeons with your party.
- **Config controls:** Dungeon theme (for The Crypt), wave/difficulty settings as applicable
- **Hero selection:** Same as PvP — pick from roster, designate controlled hero

#### Map Details
| Map | ID | Description |
|-----|----|-------------|
| Wave Arena | `wave_arena` | 20×20 wave survival — escalating enemy waves |
| Training Room | `training_room` | 20×15 practice grounds — low stakes |
| The Crypt | `wfc_dungeon` | Procedural WFC dungeon — generated floors, rooms, bosses |

### PvPvE Tab
- **Map:** The Crucible (procedural generation — dedicated PvPvE WFC variant)
- **Description:** Multiple teams clash while battling dungeon horrors. The crucible forges champions from the worthy.
- **Config controls (inherited from current PVPVE):**
  - Total Teams (2–4)
  - Monster Density (Low / Medium / High)
  - Grid Size (Medium 6×6 / Large 8×8 / XL 10×10)
  - Boss Enabled (toggle)
  - AI Rival Teams (0 to team_count-1) + per-team size sliders (1–5)
  - Dungeon Theme dropdown
- **Hero selection:** Same roster-based flow for human teams. AI rival teams use class-based selection (as today).

---

## 3. Hero Selection — New Flow

### Core Concept
The class picker is **gone**. Your class is determined by which hero you choose to control. Every hero in your roster already has a class — that's your identity in the match.

### Single Player on a Team
1. Player opens **Party Assembly** panel in the lobby
2. Sees their full alive hero roster (name, class, stats, gear preview)
3. Selects 1–5 heroes (click to add/remove)
4. **Designates one hero as "Controlled"** — click a crown/star icon or "Play As" button
   - This hero becomes the human-controlled unit
   - The player's class, stats, equipment, and abilities come from this hero
5. Remaining selected heroes spawn as AI allies with `ai_stance = "follow"`

### Multiple Humans on the Same Team
When 2+ humans share a team (e.g., both on Team A):
1. Each human picks their **controlled hero** from their own roster (1 each — mandatory)
2. Each human can **optionally** contribute additional AI heroes from their roster
3. Total team size cap: **5 units** (humans + AI heroes combined)
4. The lobby shows the team roster live — players see each other's picks
5. If the team has 2 humans and they each add AI heroes that would exceed 5, the last additions are blocked with a "Team full" indicator
6. **Coordination is visual** — players see the team fill up in real-time and adjust

**Example:** 2 humans on Team A
- Player 1: controls their Crusader, adds their Mage as AI ally (2 units)
- Player 2: controls their Ranger, adds their Hexblade + Bard as AI allies (3 units)
- Team A total: 5/5 (2 human-controlled, 3 AI hero allies)

### Locking
- Selections are **unlocked** while the player is not ready
- Clicking **Ready** locks hero selection and controlled hero designation
- Clicking **Unready** unlocks selections again

---

## 4. Lobby Layout — "War Room v2"

### Structure: Top-to-Bottom Flow

```
┌─────────────────────────────────────────────────────────────┐
│  WAR ROOM                          Match ID · Host Badge    │
│  ─────────────────────────────────────────────────────────  │
│  [ PvP ]  [ PvE ]  [ PvPvE ]          ← Mode tabs (host)   │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌─ BATTLE ORDERS (left) ──────┐  ┌─ COMMUNICATIONS ─────┐ │
│  │                             │  │                       │ │
│  │  Map: [dropdown] (if PvE)   │  │  Chat log             │ │
│  │  Theme: [dropdown]          │  │                       │ │
│  │                             │  │                       │ │
│  │  ── PvPvE Config ────────── │  │                       │ │
│  │  Teams: [2-4]               │  │                       │ │
│  │  Density: [Low/Med/High]    │  │                       │ │
│  │  Grid: [6/8/10]             │  │                       │ │
│  │  Boss: [On/Off]             │  │                       │ │
│  │  AI Rivals: [0-3] + sizes   │  │  [message input]      │ │
│  │                             │  │                       │ │
│  └─────────────────────────────┘  └───────────────────────┘ │
│                                                             │
│  ┌─ PARTY ASSEMBLY ────────────────────────────────────────┐│
│  │                                                         ││
│  │  Your Hero Roster              Selected Party (0–5)     ││
│  │  ┌──────┐ ┌──────┐ ┌──────┐   ┌──────┐ ┌──────┐       ││
│  │  │Hero 1│ │Hero 2│ │Hero 3│   │ ★ H1 │ │  H3  │ ...   ││
│  │  │Crusd.│ │Mage  │ │Rangr │   │Ctrl'd│ │ AI   │       ││
│  │  │ [+]  │ │ [+]  │ │ [+]  │   │      │ │      │       ││
│  │  └──────┘ └──────┘ └──────┘   └──────┘ └──────┘       ││
│  │                                                         ││
│  └─────────────────────────────────────────────────────────┘│
│                                                             │
│  ┌─ DEPLOYED FORCES ──────────────────────────────────────┐ │
│  │                                                        │ │
│  │  Team A (Blue)              Team B (Red)               │ │
│  │  ┌────────────────────┐     ┌────────────────────┐     │ │
│  │  │ ★ Player1 (Crusd.) │     │ ★ Player2 (Mage)  │     │ │
│  │  │   Hero3 (Ranger)   │     │   AIRival1 (Bard) │     │ │
│  │  │   Hero5 (Hexblade) │     │   AIRival2 (Rev.) │     │ │
│  │  └────────────────────┘     └────────────────────┘     │ │
│  │                                                        │ │
│  │  Team C (Green)             Team D (Gold)              │ │
│  │  └── empty ──┘              └── empty ──┘              │ │
│  │                                                        │ │
│  └────────────────────────────────────────────────────────┘ │
│                                                             │
│  ┌──────────────────────────────────────────────────────────┐│
│  │  [ Retreat ]                    [ ⚔ Ready Up / Start ]  ││
│  └──────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────┘
```

### Panel Breakdown

**Header:** Match title, match ID, host badge (⚜ Commander), headcount.

**Mode Tabs (host-only):** Three tabs at the top — PvP, PvE, PvPvE. Switching tab updates available maps and config controls. Non-hosts see the selected mode as a label.

**Battle Orders (host-only, left column):**
- Map dropdown (PvE only — PvP and PvPvE have fixed maps)
- Theme dropdown (PvE: The Crypt only; PvPvE: always shown)
- PvPvE config block (team count, density, grid, boss, AI rival teams)
- Compact — collapses irrelevant controls per mode

**Communications (right column):** Chat — same as current.

**Party Assembly (full width):**
- Left half: scrollable hero roster grid (alive heroes from your profile)
- Right half: selected party lineup (up to 5 slots)
- Each hero card shows: sprite, name, class, key stats, gear icons
- Click hero to add to party → appears in lineup
- Click hero in lineup to remove
- Crown/star icon on one hero = "Play As" (your controlled unit)
- First hero added auto-designated as controlled; can be changed
- Locked when player is Ready

**Deployed Forces (full width):**
- Shows all teams with their current composition
- Human players show ★ icon + username + class
- AI hero allies show hero name + class
- AI rival teams show AI label + class
- Team dropdown per human (A/B/C/D)
- Visual indicator for empty slots vs full teams

**Action Bar (bottom):**
- Retreat button (left)
- Ready Up / Start Match button (right)

---

## 5. Implementation Phases

All new code is built **parallel** to the existing system. The old WaitingRoom, Enter Arena, and Enter Dungeon buttons remain functional until the new system is fully tested and ready to swap in.

### Phase L1 — New Component Scaffold + Mode/Map Framework
**Files created:**
- `client/src/components/MatchLobby/MatchLobby.jsx` — main container, mode tabs, layout skeleton
- `client/src/components/MatchLobby/BattleOrders.jsx` — host config panel (map, theme, PvPvE controls)
- `client/src/components/MatchLobby/PartyAssembly.jsx` — hero roster + party builder
- `client/src/components/MatchLobby/DeployedForces.jsx` — team composition display
- `client/src/components/MatchLobby/LobbyChatPanel.jsx` — extracted chat (reuse existing logic)
- `client/src/styles/components/_match-lobby.css` — new stylesheet

**Backend:**
- Add `"the_crucible"` as a virtual map name for PvPvE procedural generation
- Update map endpoint to support curated map lists per mode (or handle client-side)
- No breaking changes to existing endpoints

**Behavior:**
- "Create Match" button in Town Hub → `POST /api/lobby/create` → opens MatchLobby
- Mode tabs switch between PvP / PvE / PvPvE and update available config
- Host config sends same `lobby_config` WS message (backward compatible)

**Tests:** Component renders, mode switching, map filtering

#### Phase L1 — Implementation Log (Completed March 14, 2026)

**Status:** ✅ Complete

**New files created:**
| File | Purpose |
|------|---------|
| `client/src/components/MatchLobby/MatchLobby.jsx` | Main lobby container — mode tabs (PvP/PvE/PvPvE), layout skeleton, header, action bar, wires up BattleOrders, LobbyChatPanel, PartyAssembly, DeployedForces. Handles mode/map switching via `lobby_config` WS message. Maps new mode tabs → existing backend `match_type` values. |
| `client/src/components/MatchLobby/BattleOrders.jsx` | Host config panel — map dropdown (PvE only), fixed map labels (PvP/PvPvE), dungeon theme selector, PvPvE config (team count, density, grid size, boss toggle, AI rival teams + sizes). Non-hosts see read-only labels. |
| `client/src/components/MatchLobby/PartyAssembly.jsx` | Phase L2 placeholder — shows "Party Assembly" header with placeholder text. Will be implemented in L2. |
| `client/src/components/MatchLobby/DeployedForces.jsx` | Team composition display — groups players by team, shows human (★) vs AI (🤖) units, team select dropdown for self, ready status indicators. Supports 2–4 teams. |
| `client/src/components/MatchLobby/LobbyChatPanel.jsx` | Extracted chat panel — auto-scrolling chat log, message input form. Reusable component (decoupled from WaitingRoom). |
| `client/src/styles/components/_match-lobby.css` | Full stylesheet — header, mode tabs, two-column layout, battle orders, chat, party assembly placeholder, deployed forces grid, action bar. Responsive at 900px breakpoint. Grimdark theme consistent. |
| `server/configs/maps/the_crucible.json` | Virtual map config for PvPvE procedural dungeon. Width/height 0 (generated at runtime). |

**Modified files:**
| File | Changes |
|------|---------|
| `client/src/App.jsx` | Added `MatchLobby` import. New `handleCreateMatch()` creates PvP match + dispatches `SET_LOBBY_MODE`/`SET_LOBBY_SELECTED_MAP` + routes to `'match_lobby'` screen. Added `match_lobby` screen rendering block. Passed `onCreateMatch` prop to TownHub. Updated screen flow comment. |
| `client/src/components/TownHub/TownHub.jsx` | Added `onCreateMatch` prop. Added "Create Match" button (ember-styled) above existing Enter Dungeon / Enter Arena buttons. Old buttons untouched. |
| `client/src/context/reducers/lobbyReducer.js` | Added `SET_LOBBY_MODE` and `SET_LOBBY_SELECTED_MAP` action handlers. |
| `client/src/context/GameStateContext.jsx` | Added `lobbyMode: 'pvp'` and `lobbySelectedMap: null` to `initialState`. |
| `client/src/styles/main.css` | Added `@import './components/_match-lobby.css'` after `_waiting-room.css`. |

**Mode → Backend mapping:**
- `pvp` tab → `match_type: 'pvp'`, `map_id: 'arena_classic'` (fixed)
- `pve` tab → `match_type: 'solo_pve'` or `'dungeon'` depending on map, `map_id` varies (wave_arena / training_room / procedural for wfc_dungeon)
- `pvpve` tab → `match_type: 'pvpve'`, `map_id: 'procedural'` (The Crucible, fixed)

**What works:**
- "Create Match" button in TownHub → creates match → opens new MatchLobby screen
- Mode tabs switch between PvP / PvE / PvPvE (host only)
- BattleOrders shows correct config per mode (map dropdown for PvE, PvPvE controls, theme selector)
- DeployedForces shows team-grouped player roster
- LobbyChatPanel handles lobby chat
- Ready/Start/Retreat buttons functional (same WS messages as WaitingRoom)
- Old WaitingRoom + Enter Arena / Enter Dungeon buttons still work unchanged

**What's deferred to L2:**
- PartyAssembly hero roster picker (placeholder only)
- `hero_roster_select` WS message
- Controlled hero designation

---

### Phase L2 — Party Assembly (Hero Roster in Lobby)
**Changes:**
- `PartyAssembly.jsx` fetches player's hero roster via `GET /api/town/roster`
- Hero selection UI: add/remove heroes, designate controlled hero
- Sends new WS message `hero_roster_select` with `{ hero_ids: [...], controlled_hero_id: "..." }`

**Backend:**
- `server/app/services/message_handlers.py` — new `handle_hero_roster_select` handler
- `server/app/core/hero_manager.py` — new `select_roster_heroes(match_id, player_id, hero_ids, controlled_hero_id)` function
  - Validates heroes exist and are alive
  - Stores controlled_hero_id in new `_controlled_hero_map`
  - Spawns non-controlled heroes as AI allies (existing `_spawn_hero_ally` logic)
  - Applies controlled hero's stats/gear to the human PlayerState
- `server/app/models/match.py` — add `controlled_hero_id` to relevant payloads

**Behavior:**
- Player sees their roster, picks heroes, designates their controlled unit
- Selections broadcast to lobby so Deployed Forces panel updates in real-time
- Locking on Ready / unlocking on Unready

**Tests:** Hero selection, validation, controlled hero designation, multi-human team cap enforcement

#### Phase L2 — Implementation Log (Completed March 14, 2026)

**Status:** ✅ Complete

**Modified files:**
| File | Changes |
|------|---------|
| `server/app/models/match.py` | Added `controlled_hero_ids: dict[str, str]` field to `MatchConfig` — maps player_id → hero_id they control. |
| `server/app/core/match_manager.py` | Added `_controlled_hero_map` shared state dict (match_id → {player_id → hero_id}). Added `select_roster_heroes` to the re-export block from hero_manager. Updated `get_lobby_players_payload()` to include `controlled_hero_id` per player from `_controlled_hero_map`. |
| `server/app/core/hero_manager.py` | Added `_controlled_hero_map` import. Raised `MAX_PARTY_SIZE` from 4 to 5. Added `select_roster_heroes(match_id, player_id, hero_ids, controlled_hero_id)` — validates heroes, applies controlled hero stats/class/equipment to human PlayerState, spawns non-controlled heroes as AI allies via `_spawn_hero_ally`, stores mappings in `_controlled_hero_map` and `MatchConfig`. |
| `server/app/services/message_handlers.py` | Added `select_roster_heroes` import. Added `handle_hero_roster_select` async handler — validates hero_ids and controlled_hero_id, calls `select_roster_heroes()`, broadcasts `hero_roster_updated` to all lobby players. Registered `"hero_roster_select"` in `MESSAGE_HANDLERS` dispatch table. |
| `client/src/components/MatchLobby/PartyAssembly.jsx` | Full implementation replacing L1 placeholder. Fetches roster via `GET /api/town/roster`. Left panel: scrollable alive hero roster grid with add/remove buttons. Right panel: selected party lineup (up to 5) with crown (👑/☆) designation for controlled hero. Auto-designates first hero added as controlled. Sends `hero_roster_select` WS message on each change. Locked when player is ready. Uses `HeroSprite` component for hero portraits. |
| `client/src/components/MatchLobby/MatchLobby.jsx` | Updated PartyAssembly props — now passes `sendAction` and `availableClasses`. Updated comment from "Phase L2 placeholder" to "Phase L2". |
| `client/src/context/GameStateContext.jsx` | Added `controlledHeroId: null` and `selectedRosterHeroes: []` to `initialState`. Added `HERO_ROSTER_UPDATED`, `SET_CONTROLLED_HERO`, `SET_SELECTED_ROSTER_HEROES` to `LOBBY_ACTIONS` set. |
| `client/src/context/reducers/lobbyReducer.js` | Added `HERO_ROSTER_UPDATED` case (updates lobbyPlayers from broadcast). Added `SET_CONTROLLED_HERO` case (sets local controlledHeroId). Added `SET_SELECTED_ROSTER_HEROES` case (sets local selectedRosterHeroes array). Updated module doc comment. |
| `client/src/App.jsx` | Added `hero_roster_updated` WS message case → dispatches `HERO_ROSTER_UPDATED`. |
| `client/src/styles/components/_match-lobby.css` | Replaced placeholder CSS with full Party Assembly styles: two-column grid layout (roster + lineup), roster cards with sprite/name/class/stats, lineup cards with crown designation button, controlled hero gold highlight, responsive breakpoint at 900px. |

**New WS message flow:**
- Client sends `hero_roster_select` → `{ type: "hero_roster_select", hero_ids: [...], controlled_hero_id: "..." }`
- Server validates via `select_roster_heroes()`, applies hero stats to player, spawns AI allies
- Server broadcasts `hero_roster_updated` → `{ type: "hero_roster_updated", player_id, hero_ids, controlled_hero_id, heroes: [...], players: {...} }`
- Client dispatches `HERO_ROSTER_UPDATED` to update lobby state

**What works:**
- PartyAssembly fetches and displays the player's alive hero roster
- Click "+" to add a hero to party (up to 5), "✕" to remove
- First hero added is auto-designated as controlled (crown icon)
- Click ☆ on any hero in lineup to switch who you play as
- Controlled hero's stats/class/equipment applied to human PlayerState on server
- Non-controlled heroes spawned as AI allies on player's team
- Selections broadcast to all lobby players (Deployed Forces updates)
- Selections locked when player clicks Ready, unlocked on Unready
- All 3792 existing tests pass — no regressions

**What's deferred to L3:**
- Multi-human team coordination (team cap of 5 across multiple humans)
- "Team Full" indicator blocking over-filling
- Owner labels on contributed AI heroes

---

### Phase L3 — Multi-Human Team Coordination
**Changes:**
- `DeployedForces.jsx` shows live team composition across all players
- Team slot counter: shows `N/5` for each team
- When a team hits 5 units, block further hero additions with "Team Full" feedback
- Each human's contributed AI heroes are labeled with the owner's name

**Backend:**
- `hero_manager.py` — enforce per-team cap of 5 across multiple human players
  - `get_team_slots_remaining(match_id, team)` counts humans + hero allies on that team
  - Reject hero additions that would exceed team cap
  - Broadcast updated team state after each change

**Behavior:**
- 2 humans on Team A each pick their controlled hero + optional AI heroes
- Live updates show the team filling up
- "Team Full" indicator prevents over-filling

**Tests:** Multi-human team scenarios, cap enforcement, re-selection after unready

#### Phase L3 — Implementation Log (Completed March 14, 2026)

**Status:** ✅ Complete

**Modified files:**
| File | Changes |
|------|---------|
| `server/app/core/hero_manager.py` | Added `MAX_TEAM_SIZE = 5` constant. Added `get_team_slots_remaining(match_id, team)` — counts humans + AI allies on a team, returns remaining slots. Added `get_all_team_slots(match_id)` — returns `{team: {used, max, remaining}}` dict for all 4 teams. Added team cap enforcement in `select_roster_heroes()` — after removing old allies, checks remaining team slots and trims hero list if ally additions would exceed cap (controlled hero keeps its existing slot, only allies need new ones). Fixed `_remove_hero_ally()` bug — was only removing from `team_a`, now removes from all team lists (`team_a`/`team_b`/`team_c`/`team_d`). `select_roster_heroes()` return dict now includes `team_slots` field. |
| `server/app/core/match_manager.py` | Added `MAX_TEAM_SIZE`, `get_team_slots_remaining`, `get_all_team_slots` to re-export block from hero_manager. Updated `get_lobby_players_payload()` to include `owner_username` field for AI hero allies (reads from `_hero_ally_map`). |
| `server/app/services/message_handlers.py` | Updated `handle_hero_roster_select` broadcast to include `team_slots` from `select_roster_heroes()` return value. |
| `client/src/components/MatchLobby/DeployedForces.jsx` | Added `teamSlots` prop. Live N/5 counter now uses server-provided slot data when available. Added `deployed-team--full` class + red border/shadow when team is at capacity. Added "Team Full" indicator banner (only shown for the player's own team). Added `owner_username` label on contributed AI heroes (e.g., "(Player1's hero)"). |
| `client/src/components/MatchLobby/PartyAssembly.jsx` | Added `teamSlots` and `playerTeam` props. Computes `teamRemaining` from server-provided slot data. `handleAddHero()` now blocks additions when team has no remaining slots (beyond first hero). Roster cards show disabled state with "Team full (5 units max)" tooltip when team-blocked. "Selected Party" section shows team-full warning banner when team is at capacity. |
| `client/src/components/MatchLobby/MatchLobby.jsx` | Reads `teamSlots` from game state. Computes `playerTeam` from lobby players. Passes `teamSlots` to both `PartyAssembly` and `DeployedForces`. Passes `playerTeam` to `PartyAssembly`. |
| `client/src/context/reducers/lobbyReducer.js` | Updated `HERO_ROSTER_UPDATED` case to store `teamSlots` from payload (`action.payload.team_slots`). Updated module doc comment to include `SET_LOBBY_MODE`, `SET_LOBBY_SELECTED_MAP`. |
| `client/src/context/GameStateContext.jsx` | Added `teamSlots: null` to `initialState`. Added `SET_LOBBY_MODE` and `SET_LOBBY_SELECTED_MAP` to `LOBBY_ACTIONS` routing set (latent L1 fix). |
| `client/src/styles/components/_match-lobby.css` | Added `.deployed-team-count--full` (red highlight for full team count). Added `.deployed-team--full` (red border + box-shadow). Added `.deployed-team-full-indicator` (centered "Team Full" banner). Added `.deployed-unit-owner` (dim italic style for hero owner labels). Added `.party-assembly-team-full` (red warning banner in party assembly). |

**Team cap enforcement flow:**
1. Player sends `hero_roster_select` with `hero_ids` + `controlled_hero_id`
2. Server calls `select_roster_heroes()` which:
   - Removes existing hero allies for this player (`_remove_hero_ally`)
   - Counts remaining team slots via `get_team_slots_remaining(match_id, player_team)`
   - The controlled hero uses the player's existing slot (no new slot needed)
   - Ally heroes need new slots — if ally_count > team_remaining, trims to fit
   - Spawns allowed allies, returns result with `team_slots` dict
3. Handler broadcasts `hero_roster_updated` including `team_slots` to all lobby clients
4. Client `lobbyReducer` stores `teamSlots` in state
5. `PartyAssembly` reads `teamSlots[myTeam].remaining` — blocks further additions when 0
6. `DeployedForces` shows live N/5 count + "Team Full" indicator using `teamSlots`

**Bug fix included:**
- `_remove_hero_ally()` previously only removed AI hero IDs from `match.team_a`. Now iterates all four team lists (`team_a`/`team_b`/`team_c`/`team_d`) — fixes team corruption when hero allies are on non-A teams.

**Latent L1 fix included:**
- `SET_LOBBY_MODE` and `SET_LOBBY_SELECTED_MAP` actions were handled by `lobbyReducer` but not listed in `LOBBY_ACTIONS` set in `GameStateContext.jsx`, so they fell through to the default combiner instead of the lobby reducer. Now properly routed.

**What works:**
- Team cap of 5 enforced server-side across multiple humans on the same team
- Server trims hero lists that would exceed remaining team slots
- Live team slot counts broadcast to all lobby clients after every roster change
- "Team Full" indicator appears in both Deployed Forces and Party Assembly
- Owner labels shown on contributed AI heroes (e.g., "(Player1's hero)")
- Roster card add buttons disabled with appropriate tooltip when team is full
- All 3710 existing tests pass — no regressions (1 pre-existing unrelated failure in test_phase16d_unique_items.py)

**What's deferred to L4:**
- Mode-specific config controls (PvP/PvE/PvPvE tab filtering)
- Map assignment validation per mode

---

### Phase L4 — Mode-Specific Config & Map Filtering
**Changes:**
- PvP tab: no map dropdown (Arena Classic hardcoded), minimal config (team assignment)
- PvE tab: map dropdown (Wave Arena / Training Room / The Crypt), theme selector for The Crypt
- PvPvE tab: no map dropdown (The Crucible hardcoded), full PVPVE config controls
  - Team count, monster density, grid size, boss toggle, AI rival teams + sizes

**Backend:**
- Consolidate mode types: `pvp`, `pve`, `pvpve` (map to existing match_type for backward compat)
  - `pve` maps to `dungeon` or `solo_pve` internally depending on map
  - `pvpve` maps to existing `pvpve` type
  - `pvp` stays as `pvp`
- The Crucible uses existing `_start_pvpve_match()` pipeline

**Behavior:**
- Switching tabs updates available controls and map selection
- Config persists within a tab but resets when switching modes

**Tests:** Mode switching, config visibility per mode, map assignment

#### Phase L4 — Implementation Log (Completed March 14, 2026)

**Status:** ✅ Complete

**Modified files:**
| File | Changes |
|------|---------|
| `client/src/components/MatchLobby/MatchLobby.jsx` | Added `MODE_DEFAULT_CONFIGS` lookup — per-mode default config objects used to reset server state when switching tabs. Updated `handleModeChange()` to send full config reset (all mode-specific fields) via `lobby_config` WS message instead of just `match_type` + `map_id`. PvP defaults to `arena_classic` with `ai_opponents: 0`, PvE defaults to `procedural` with dungeon type, PvPvE sends full defaults (`pvpve_team_count: 2`, `pvpve_pve_density: 0.5`, etc.). |
| `client/src/components/MatchLobby/BattleOrders.jsx` | PvP fixed map display now also shows a `config-row--minimal` hint: "Team assignment only — configure teams in Deployed Forces below." Provides user guidance that PvP has no config controls beyond team selection. |
| `client/src/context/reducers/lobbyReducer.js` | Updated `CONFIG_CHANGED` case: now derives `lobbyMode` from incoming `match_type` (`pvp` → `pvp`, `solo_pve`/`dungeon`/`mixed` → `pve`, `pvpve` → `pvpve`) and `lobbySelectedMap` from `map_id` (maps `procedural` back to `wfc_dungeon` or `the_crucible` based on mode). Non-host players now stay synced when host switches mode tabs. Updated module doc comment with Phase L4 note. |
| `server/app/core/match_manager.py` | **Mode-switch reset:** `update_match_config()` now detects when `match_type` changes and resets irrelevant config fields. PVP: clears AI counts, theme, and all PvPvE fields. PVE (solo_pve/dungeon): clears PvPvE fields. PVPVE: resets PvPvE fields to defaults (team_count=2, density=0.5, boss=true, grid=8, ai_team_count=0). **Map validation per mode:** Added `_mode_allowed_maps` dict mapping each `MatchType` to its set of allowed `map_id` values. PVP allows only `arena_classic`, PVE allows `wave_arena`/`training_room`/`procedural`, PVPVE allows only `procedural`, MIXED has no restriction (legacy compat). Map changes are rejected if the map isn't in the allowed set for the current (or incoming) mode. The `procedural` virtual map ID is accepted without file-on-disk validation. |
| `server/tests/test_chunk3.py` | Updated `test_host_can_change_map` test: changed from PVP (which now only allows `arena_classic`) to MIXED mode so the "maze" map change is still valid. Test validates the general map-change mechanism outside of L4's per-mode restrictions. |
| `client/src/styles/components/_match-lobby.css` | Added `.config-row--minimal` style — subtle separator + spacing for PvP's "team assignment only" hint message. |

**Mode-switch config reset flow:**
1. Host clicks a mode tab (e.g., PvPvE → PvP)
2. `handleModeChange('pvp')` sends `lobby_config` with full `MODE_DEFAULT_CONFIGS['pvp']` object:
   `{ match_type: 'pvp', map_id: 'arena_classic', ai_opponents: 0, ai_allies: 0, theme_id: null }`
3. Server `update_match_config()` processes `match_type` change — detects `PVPVE → PVP` transition:
   - Clears AI counts, theme, resets all PvPvE fields to defaults
4. Server broadcasts `config_changed` with full updated config to all clients
5. Non-host clients receive `CONFIG_CHANGED` — `lobbyReducer` derives `lobbyMode: 'pvp'` from `match_type: 'pvp'` and `lobbySelectedMap: 'arena_classic'` from `map_id`
6. BattleOrders re-renders with PvP-appropriate controls (fixed map label, minimal hint)

**Per-mode map validation:**
| Mode | Allowed Maps |
|------|-------------|
| PVP | `arena_classic` |
| SOLO_PVE | `wave_arena`, `training_room`, `procedural` |
| DUNGEON | `procedural`, `wave_arena`, `training_room` |
| PVPVE | `procedural` |
| MIXED | Any (legacy, no restriction) |

**What works:**
- Switching mode tabs sends full config reset → server clears irrelevant fields
- Non-host players see mode changes in real-time (lobbyMode/lobbySelectedMap derived from CONFIG_CHANGED)
- PvP tab shows fixed "Arena Classic" map + "team assignment only" hint
- PvE tab shows map dropdown (3 maps) + theme selector (for The Crypt only)
- PvPvE tab shows fixed "The Crucible" map + all PvPvE config controls
- Server validates map_id against allowed maps per mode — rejects invalid assignments
- Config persists within a tab (unchanged fields stay) but resets on mode switch
- All 3764 existing tests pass — no regressions

**What's deferred to L5:**
- Remove old "Enter Arena" / "Enter Dungeon" buttons from TownHub
- Route all match creation through new lobby
- Notice Board join flow → new MatchLobby
- CSS polish, responsive layout, animations
- Archive deprecated WaitingRoom components

---

### Phase L5 — Integration, Polish & Cutover
**Changes:**
- Remove "Enter Arena" and "Enter Dungeon" buttons from TownHub
- Replace with single "Create Match" button
- Route `screen='waiting'` to new `MatchLobby` instead of old `WaitingRoom`
- Update Notice Board join flow to route into new lobby
- Hide deprecated maps from any remaining endpoints
- Update `lobbyReducer.js` for new state fields (`controlled_hero_id`, mode tabs)
- CSS polish: grimdark theme consistency, responsive layout, animations

**Cleanup (deferred — after validation):**
- Archive old `WaitingRoom.jsx` and `_waiting-room.css`
- Remove `selectedHeroIds` dungeon pre-selection from TownHub/HeroRoster
- Remove class_select UI and handler (class comes from controlled hero)
- Remove deprecated map files from configs/maps/ (keep files, just hide from UI)

**Tests:** Full end-to-end flow, join existing match, multi-player scenarios, all 3 modes

#### Phase L5 — Implementation Log (Completed March 15, 2026)

**Status:** ✅ Complete

**Modified files:**
| File | Changes |
|------|---------|
| `client/src/App.jsx` | Removed `handleEnterArena()` and `handleEnterDungeon()` functions — all match creation now routes through `handleCreateMatch()`. Updated `handleJoinMatch()` to route to `match_lobby` screen instead of `waiting`, and to derive+dispatch `lobbyMode` and `lobbySelectedMap` from the joined match's config. Changed `screen === 'waiting'` rendering block to render `MatchLobby` instead of `WaitingRoom` (backward compat). Removed `onEnterArena`/`onEnterDungeon` props from TownHub. Updated screen flow comment to reflect L5 routing. |
| `client/src/components/TownHub/TownHub.jsx` | Removed `onEnterArena` and `onEnterDungeon` props. Removed `selectedHeroIds` state variable. Removed `handleEnterDungeon()` and `handleHeroSelected()` functions. Simplified `handleJoinMatch()` — removed dungeon hero requirement check (hero selection now happens in the lobby). Removed "Enter Dungeon" and "Enter Arena" buttons from sidebar actions — only "Create Match" remains. Removed dungeon-specific warnings from Notice Board (isDungeon checks, "Select heroes first", hero count hint). Removed `onSelectHero` prop passed to HeroRoster. |
| `client/src/components/TownHub/HeroRoster.jsx` | Removed `onSelectHero` prop. Removed `useGameDispatch` import and `dispatch` variable (no longer needed). Removed `selectedHeroIds` state tracking. Removed `handleSelect()` function. Removed party counter ("Party: X/4 selected"). Removed selection badge ("✓ #N") from hero card headers. Removed "Select for Dungeon" button entirely from hero card footer — only "Manage Gear" remains. Removed `onSelectHero` prop passed to HeroDetailPanel. Updated module doc comment. |
| `client/src/components/TownHub/HeroDetailPanel.jsx` | Removed `onSelectHero` prop. Removed `isSelected`, `selectionIndex`, `canSelect` computed variables. Removed `handleSelectForDungeon()` function. Removed "Select for Dungeon" button from the detail panel left column. |
| `client/src/components/MatchLobby/DeployedForces.jsx` | Added `data-team` attribute to team containers for CSS team-color styling. |
| `server/app/routes/maps.py` | Added `_HIDDEN_MAPS` set containing 11 deprecated map IDs. Updated `list_maps()` endpoint to skip maps in the hidden set — maps remain on disk but are no longer returned by the API. |
| `client/src/styles/components/_match-lobby.css` | Added Phase L5 polish: `@keyframes lobby-fade-in` entrance animation with staggered delays for header/tabs/columns/sections/action-bar. Active mode tab box-shadow glow. Card hover lift+shadow transitions for roster and lineup cards. Deployed unit hover highlight. `@keyframes action-pulse` for Start/Ready buttons. Team-specific border colors via `data-team` attribute (`a`=blue, `b`=red, `c`=green, `d`=gold). Updated file header comment. |

**Cutover routing changes:**
1. **"Create Match"** → `handleCreateMatch()` → `POST /api/lobby/create` → `screen='match_lobby'` (unchanged from L1)
2. **Notice Board "Join"** → `handleJoinMatch(matchId)` → `POST /api/lobby/join/{id}` → derives `lobbyMode` from `match_type` → `screen='match_lobby'` (was `screen='waiting'`)
3. **`screen='waiting'`** → now renders `MatchLobby` instead of `WaitingRoom` (backward compat for any residual code paths)

**Deprecated UI elements removed:**
- "Enter Arena" button (crimson, TownHub sidebar)
- "Enter Dungeon" button (verdant, TownHub sidebar, with hero count badge)
- "Select for Dungeon" button (HeroRoster hero cards + HeroDetailPanel)
- Party counter "Party: X/4 selected" (HeroRoster)
- Selected badge "✓ #N" (HeroRoster hero card headers)
- Dungeon hero requirement check on Notice Board join
- "Select heroes first" warning on dungeon match listings
- Hero count hint below Notice Board listings

**Hidden maps (no longer returned by `/api/maps/`):**
`open_arena`, `open_arena_small`, `open_arena_large`, `maze`, `maze_large`, `islands`, `islands_large`, `dungeon_test`, `open_catacombs`, `test_xl`, `wfc_dungeon_6x6_test`

**What works:**
- Single "Create Match" button in TownHub → opens new MatchLobby with mode tabs
- Notice Board join → opens new MatchLobby with correct mode derived from match config
- All match creation flows route through unified MatchLobby
- Old WaitingRoom component still exists on disk but is no longer rendered
- Hero roster in TownHub is now view-only with gear management (no dungeon selection)
- Deprecated maps hidden from API but files preserved on disk
- CSS entrance animations, hover effects, and action button pulse in MatchLobby

**What's deferred (post-validation cleanup):**
- Archive/delete `WaitingRoom.jsx` and `_waiting-room.css`
- Remove `WaitingRoom` import from `App.jsx`
- Remove `SELECT_HERO` action handler from game state context
- Remove `selectedHeroIds` from initial state
- Remove `class_select` WS handler and class selector UI (class comes from controlled hero)
- Remove deprecated map JSON files from `server/configs/maps/`

---

## 6. New WebSocket Messages

| Message | Direction | Payload | Purpose |
|---------|-----------|---------|---------|
| `hero_roster_select` | Client → Server | `{ hero_ids: [str], controlled_hero_id: str }` | Select heroes from roster + designate controlled unit |
| `hero_roster_updated` | Server → All | `{ player_id, hero_ids, controlled_hero_id, heroes: [...], players }` | Broadcast roster selection to lobby |

Existing messages that continue working unchanged:
- `lobby_config` — host config changes
- `team_select` — team assignment
- `ready` — ready/start
- `chat_message` — lobby chat
- `hero_select` — **deprecated but kept for backward compat** during transition

---

## 7. Data Model Changes

### MatchConfig Additions
```python
# New field
controlled_hero_ids: dict[str, str] = {}  # player_id → hero_id they control
```

### Match Manager State Additions
```python
_controlled_hero_map: dict[str, dict[str, str]] = {}  # match_id → {player_id → hero_id}
```

### Lobby Reducer State Additions
```javascript
// New fields in lobby state
lobbyMode: 'pvp' | 'pve' | 'pvpve',        // active mode tab
controlledHeroId: null,                       // local player's controlled hero
selectedRosterHeroes: [],                     // local player's selected hero IDs
```

---

## 8. File Inventory

### New Files (built alongside existing)
| File | Purpose |
|------|---------|
| `client/src/components/MatchLobby/MatchLobby.jsx` | Main lobby container + mode tabs |
| `client/src/components/MatchLobby/BattleOrders.jsx` | Host config panel |
| `client/src/components/MatchLobby/PartyAssembly.jsx` | Hero roster picker + controlled hero |
| `client/src/components/MatchLobby/DeployedForces.jsx` | Team composition display |
| `client/src/components/MatchLobby/LobbyChatPanel.jsx` | Chat panel (extracted) |
| `client/src/styles/components/_match-lobby.css` | New lobby styles |

### Modified Files (phased changes)
| File | Changes |
|------|---------|
| `client/src/App.jsx` | New "Create Match" handler, route to MatchLobby |
| `client/src/components/TownHub/TownHub.jsx` | Replace two buttons with one "Create Match" button |
| `client/src/context/reducers/lobbyReducer.js` | New state fields + actions |
| `server/app/services/message_handlers.py` | New `handle_hero_roster_select` handler |
| `server/app/core/hero_manager.py` | `select_roster_heroes()` with controlled hero logic |
| `server/app/core/match_manager.py` | `_controlled_hero_map`, team cap enforcement |
| `server/app/models/match.py` | `controlled_hero_ids` on MatchConfig |

### Untouched During Build (old system stays functional)
| File | Status |
|------|--------|
| `client/src/components/WaitingRoom/WaitingRoom.jsx` | Kept until cutover |
| `client/src/components/Lobby/Lobby.jsx` | Kept (login screen unchanged) |
| `client/src/styles/components/_waiting-room.css` | Kept until cutover |
| All existing map JSON files | Kept on disk, just hidden from new UI |

---

## 9. Map Reference

### Active Maps (shown in new lobby)
| Display Name | ID | Mode Tab | Type |
|--------------|----|----------|------|
| Arena Classic | `arena_classic` | PvP | arena |
| Wave Arena | `wave_arena` | PvE | dungeon |
| Training Room | `training_room` | PvE | dungeon |
| The Crypt | `wfc_dungeon` | PvE | dungeon (procedural WFC) |
| The Crucible | `the_crucible` | PvPvE | dungeon (procedural PvPvE WFC) |

### Hidden Maps (kept on disk, removed from UI)
`open_arena`, `open_arena_small`, `open_arena_large`, `maze`, `maze_large`, `islands`, `islands_large`, `dungeon_test`, `open_catacombs`, `test_xl`, `wfc_dungeon_6x6_test`

---

## 10. Migration Strategy

1. **Build phases L1–L4** with the old system fully intact. New lobby is accessible via a new "Create Match" button added *alongside* the existing buttons during development.
2. **Internal testing** on the new lobby while old lobby remains the default.
3. **Phase L5 cutover**: Remove old buttons, route all match creation through the new lobby.
4. **Post-cutover cleanup**: Archive deprecated components, remove class_select dead code, clean up old hero pre-selection flow in TownHub.

This ensures zero downtime — the working game is never broken during development.
