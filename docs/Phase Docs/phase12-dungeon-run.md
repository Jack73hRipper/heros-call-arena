# Phase 12: The Dungeon Run — Design Document

## Overview

**Goal:** Close the gameplay loop. Turn the existing combat, loot, town, and hero systems into a complete *dungeon run* experience with escalating floors, extraction via portal scroll, procedural layouts, crowd control, and full class skill kits.

**Theme:** Risk-vs-reward roguelite dungeon crawling — push deeper for better loot, or escape before permadeath takes everything.

**Status:** In Progress — Features 1–2 complete, Feature 3 in progress (particle lab upgraded, presets created)  
**Prerequisites:** Phase 11 complete (Class Identity & Enemy Expansion — 1495+ tests passing)

---

## Core Vision

Right now the game has excellent combat, party AI, loot, hero persistence, permadeath, a town economy, and procedural dungeon tooling — but these pieces don't yet chain together into a **replayable loop**. Phase 12 connects them.

**The Complete Loop:**
1. Town Hub → hire heroes, buy gear & potions, equip party
2. Enter Dungeon → procedurally generated Floor 1
3. Fight through rooms, collect loot, manage resources
4. Clear floor boss → choice: **portal out** (keep loot) or **descend** (harder floor, better rewards)
5. Permadeath is always lurking — push too deep and lose everything
6. Survive → return to town with loot haul, gear up, go again

---

## Feature Summary

| # | Feature | Category | Scope | Status |
|---|---------|----------|-------|--------|
| 1 | Complete Crusader & Ranger Skill Kits | Class Balance | 7 new skills, including CC | ✅ Done |
| 2 | Crowd Control / Status Effects | Combat Depth | Stun, Slow, Taunt, Evasion | ✅ Done |
| 3 | Portal Scroll — Extraction Mechanic | Core Loop | Channeled cast + ground portal + extraction | ✅ Done |
| 4 | Multi-Floor Dungeon Progression | Core Loop | 3–5 floors per run, scaling difficulty | ✅ Done |
| 5 | Procedural Dungeon Integration | Replayability | Wire WFC generation into match flow | Planned |
| 6 | Rare Item Tier & Loot Expansion | Loot Motivation | New rarity tier, deeper = better drops | Planned |
| 7 | Mini-Map & Explored Tile Memory | QoL / Navigation | Small overlay showing explored areas | Planned |
| 8 | Sound & Audio Foundation | Polish / Feel | Minimal ambient + combat SFX pass | Planned |

---

## Feature 1: Complete Crusader & Ranger Skill Kits ✅

**Status:** Implemented  
**Tests:** 53 dedicated tests in `test_phase12_skills.py`, 220 skill-related tests passing

**Problem:** Crusader had 2 skills, Ranger had 1. Every other class has 4. These two classes felt incomplete and one-dimensional in longer dungeon runs.

**Result:** Both classes now have 4 active skills + auto-attack (5 total). Crusader lost `double_strike` and `war_cry` (kept by werewolf enemy class) and gained a dedicated tank kit. Ranger kept `power_shot` and gained 3 new battlefield-control skills.

### Crusader — Final Kit

| Skill | Type | Targeting | Cooldown | Key Stats |
|-------|------|-----------|----------|-----------|
| Auto Attack (Melee) | melee | adjacent | — | — |
| **Taunt** | taunt debuff | self (2-tile radius) | 5 turns | 2-turn taunt on all nearby enemies |
| **Shield Bash** | stun_damage | adjacent enemy | 4 turns | 0.7× melee damage + 1-turn stun |
| **Holy Ground** | aoe_heal | self (1-tile radius) | 5 turns | 15 HP to all allies in radius |
| **Bulwark** | buff | self | 5 turns | +8 armor for 4 turns |

**Design:** Crusader is now a pure tank — Taunt forces aggro, Shield Bash controls single targets, Holy Ground provides sustain, Bulwark hardens defenses. No DPS skills; damage comes from auto-attack only.

### Ranger — Final Kit

| Skill | Type | Targeting | Cooldown | Key Stats |
|-------|------|-----------|----------|-----------|
| Auto Attack (Ranged) | ranged | ranged enemy | — | — |
| **Power Shot** | ranged_damage | ranged enemy | 5 turns | 1.8× ranged damage |
| **Volley** | aoe_damage | ground (2-tile radius) | 5 turns | 0.5× ranged damage, range 5 |
| **Evasion** | evasion buff | self | 6 turns | 2 dodge charges, 4-turn duration |
| **Crippling Shot** | ranged_damage_slow | ranged enemy | 5 turns | 0.8× ranged damage + 2-turn slow |

**Design:** Ranger excels at kiting and area denial — Volley punishes clusters, Crippling Shot slows pursuers, Evasion buys time when enemies close in, Power Shot provides burst.

### Files Modified

- `server/configs/skills_config.json` — 7 new skill definitions, updated `class_skills` and `allowed_classes`
- `server/app/core/skills.py` — CC helpers, 6 new effect handlers, dispatcher update, evasion tick support
- `server/app/core/turn_resolver.py` — stun/slow guards on 4 resolution phases, evasion dodge checks, AoE kill tracking
- `server/app/core/ai_skills.py` — rewrote `_tank_skill_logic` and `_ranged_dps_skill_logic`
- `server/app/core/ai_memory.py` — taunt enforcement in `_pick_best_target`
- `server/app/core/ai_behavior.py` — stun check in `decide_ai_action`
- `client/src/components/BottomBar/SkillIconMap.js` — emoji fallbacks for 7 new skills

---

## Feature 2: Crowd Control / Status Effects ✅

**Status:** Implemented (integrated with Feature 1)  
**Tests:** CC helpers, buff tick/expiry, and guard behavior all tested in `test_phase12_skills.py`

**Problem:** All combat was damage-focused. No way to disable, slow, or lock down enemies.

**Result:** Four CC types implemented using the existing `active_buffs` system. Turn resolver enforces CC at all relevant phases.

### Status Effects Implemented

| Effect | Duration | Blocks | Applied By |
|--------|----------|--------|------------|
| **Stun** | 1 turn | Movement, skills, ranged, melee (all actions) | Shield Bash |
| **Slow** | 2 turns | Movement only (can still attack/use skills) | Crippling Shot |
| **Taunt** | 2 turns | Forces AI to target taunter (advisory for humans) | Taunt |
| **Evasion** | 2 charges / 4 turns | Negates incoming melee or ranged attacks | Evasion |

### CC System Details

- **Buff-based:** All CC uses `PlayerState.active_buffs` with a `type` field (`stun`, `slow`, `taunt`, `evasion`)
- **No stacking:** Re-applying the same CC type refreshes duration instead of stacking
- **Tick & expiry:** `tick_buffs()` decrements `turns_remaining` each turn; expired buffs auto-removed
- **Evasion charges:** Follows Ward pattern — charge-based with a time limit. Charges consumed on dodge, buff removed when charges or turns hit 0
- **Turn resolver guards:** Stun blocks phases 1 (movement), 1.9 (skills), 2 (ranged), 3 (melee). Slow blocks phase 1 only.
- **Evasion dodge:** Checked in phases 2 (ranged) and 3 (melee) — if defender has evasion charges, attack is dodged and charge consumed
- **AI enforcement:** Stunned AI returns WAIT action. Taunted AI forced to target taunter via `_pick_best_target`.
- **Root deferred:** Root was in the original plan but not implemented — Slow covers the same gameplay niche with simpler semantics. Can add Root later if needed for boss abilities.

### New Helper Functions (`skills.py`)

- `is_stunned(player)` → bool
- `is_slowed(player)` → bool  
- `is_taunted(player)` → (bool, source_id)
- `get_evasion_effect(player)` → dict | None
- `trigger_evasion_dodge(defender)` → bool (consumes charge)

---

## Feature 3: Portal Scroll — Extraction Mechanic ✅

**Status:** Implemented — Backend portal system, client extraction UX, and AI portal retreat all complete  
**Tests:** 20 dedicated tests in `test_portal_scroll.py`, all passing  
**Prerequisite Work:** Compound Preview Mode added to Particle Effects Lab

**Problem:** Portal scrolls exist in the loot tables and item config but the current implementation is trivially simple — using the scroll instantly ends the match with `winner = "dungeon_extract"`. No cast time, no physical portal entity, no player agency, and no dedicated visual effect (uses generic heal-pulse or nothing).

**Goal:** Transform portal scrolls into a rich, tension-building extraction mechanic — the *heart* of the risk-vs-reward loop.

### Finalized Design

#### Channeled Cast (3 Turns)
- Using a portal scroll from inventory begins a **3-turn channel**
- The caster is **locked in place** during channeling — cannot move, attack, or use skills
- Channeling is **uninterruptible** — once started, the portal WILL open (enemies can still damage the caster during the channel, creating urgency to protect them)
- The scroll is **consumed when channeling begins** (committed action)
- A `portal-channel-swirl` particle effect plays on the caster during the channel

#### Portal Entity on Ground
- After the 3-turn channel completes, a **portal entity spawns on the caster's tile**
- The portal is a persistent map object (similar to doors/chests) — rendered on the dungeon layer
- A `portal-open-flash` burst plays when it materializes, followed by a looping `portal-ground-ring` + `portal-core-glow` + `portal-rising-sparks` compound effect
- The portal **persists for 20 turns**, then fades away
- A turn counter displays on the portal showing remaining turns

#### Voluntary Extraction via Interaction
- Any allied player/hero can **walk to the portal tile** and press **E to interact**
- An interaction prompt appears: **"Return to safety?"** with Confirm / Cancel
- On confirm, that hero is **extracted** — removed from play, flagged as safely escaped with all their loot and gold
- Extraction is **per-hero, not party-wide** — the party can split; some extract while others keep fighting
- AI-controlled party members on the portal tile auto-extract after 1 turn (configurable)

#### Match Resolution
- When all remaining heroes have either **extracted** or **died**, the match ends
- Extracted heroes return to town with their loot haul
- Dead heroes suffer permadeath as normal
- Run summary shows: heroes extracted, heroes lost, loot collected, floors cleared

### Backend Implementation Plan

**New state fields:**
- `MatchState.portal`: `{ active: bool, tile: [x,y], turns_remaining: int, owner_id: str }` or `null`
- `MatchState.channeling`: `{ player_id: str, action: "portal", turns_remaining: int }` or `null`
- `PlayerState.extracted`: `bool` (default `false`)

**Turn resolver changes:**
- New phase `_resolve_channeling()` between items and movement — decrements channel timer, spawns portal when complete
- Channel guard: channeling players skip movement, skills, ranged, melee phases
- Portal tick: decrement `portal.turns_remaining` each turn; remove portal when 0
- Extracted players skip all phases (treated as removed from play, not dead)

**New WebSocket message:** `INTERACT` with `type: "enter_portal"` → triggers extraction for that player

**New action type:** `ActionType.INTERACT` (or reuse `USE_ITEM` with a subtype)

### Client Implementation Plan

**Portal rendering:** New portal tile type in `dungeonRenderer.js` — simple animated sprite or colored glow tile with particle overlay

**Interaction system:** When player is on a portal tile, show an `[E] Enter Portal` prompt in the HUD. Press E sends `INTERACT` message.

**Channeling UI:** Show a channeling bar above the caster (3 turns → 2 → 1 → portal opens). Skill bar grayed out during channel.

**Particle effects:** Wire new portal presets into `particle-effects.json` effect mappings

### Particle Lab Upgrade (Completed)

A **Compound Effect Preview Mode** was added to the Particle Effects Lab to support designing multi-layer effects like the portal:

**New features:**
- **Mode Toggle** in toolbar: switches between Single Preset mode (original) and Compound mode
- **Layer List** (`CompoundPanel.jsx`): add presets from the library as layers, toggle visibility per layer, reorder with up/down, duplicate, remove
- **Compound Canvas** (`CompoundCanvas.jsx`): renders all visible layers simultaneously at the canvas center, auto-emit restarts all layers together
- **Per-layer offset controls**: X/Y pixel offset for positioning layers relative to center
- **Layer editing**: click a layer to load its preset into the right-side control panel; edits sync back to the layer in real-time
- **Export Map Entry**: one-click export generates the `particle-effects.json` format (`effect` + `extras` array) to clipboard
- **Persistent state**: compound layers saved to localStorage across sessions

**Files created:**
- `tools/particle-lab/src/components/CompoundPanel.jsx` — layer management UI
- `tools/particle-lab/src/components/CompoundCanvas.jsx` — multi-layer preview renderer

**Files modified:**
- `tools/particle-lab/src/App.jsx` — compound mode state, layer sync, mode switching
- `tools/particle-lab/src/components/Toolbar.jsx` — compound mode toggle button
- `tools/particle-lab/src/styles/lab.css` — full CSS for compound panel, layers, offsets, dropdowns

### New Portal Particle Presets (Completed)

5 new presets designed to be stacked as compound layers:

| Preset | Type | Purpose | Key Properties |
|--------|------|---------|----------------|
| `portal-ground-ring` | Looping | Base ring on the ground | Ring spawn, 22/sec, purple→blue gradient, trails |
| `portal-core-glow` | Looping | Bright center pulse | Circle spawn (r=5), white→blue, large particles |
| `portal-rising-sparks` | Looping | Floating upward sparks | Star shape, upward angle, purple/gold, trails |
| `portal-channel-swirl` | Looping | Cast-time effect on caster | Fast ring, spray upward, white→purple, elastic easing |
| `portal-open-flash` | One-shot | Burst when portal materializes | 35-particle burst, white→purple |

Presets added to both:
- `tools/particle-lab/src/presets.js` (lab built-in library)
- `client/public/particle-presets.json` (game runtime — 32 total presets)

### Effect Mapping (To Be Wired)

When the backend implementation is complete, add to `client/public/particle-effects.json`:

```json
"items": {
  "use_potion": { ... },
  "portal_channel": {
    "effect": "portal-channel-swirl",
    "target": "caster",
    "follow": true,
    "loopDuration": 3.0
  },
  "portal_open": {
    "effect": "portal-ground-ring",
    "target": "tile",
    "extras": ["portal-core-glow", "portal-rising-sparks", "portal-open-flash"]
  }
}
```

### Open Questions Resolved

| Question | Decision | Rationale |
|----------|----------|-----------|
| Cast time | 3-turn channel, uninterruptible | Creates tension without frustration; protectable by party |
| Scroll consumed when? | On channel start | Committed action — prevents infinite retry abuse |
| Party-wide or individual? | Individual extraction | More strategic depth — split decisions, sacrifice plays |
| Portal duration | 20 turns | Long enough to push ahead and run back; not permanent |
| Mid-floor or boss-only? | Anytime | Portal is your emergency exit *and* your victory condition |
| Visual effect | New compound effect (5 presets) | Designed in upgraded Particle Lab with compound preview |
| Interruption | Cannot be interrupted | Guarantees the portal opens; damage still applies to caster |
| AI retreat | Immediate pathfind to portal | Hero allies auto-retreat when portal opens — no manual control needed |

### Backend Implementation (Completed)

**Turn Resolver — 4 new phases** (`server/app/core/turn_resolver.py`):
- **Phase 0 (Items):** Portal scroll consumed immediately, starts 3-turn channeling via `portal_context`
- **Phase 0.25 (`_resolve_channeling`):** Ticks channel timer each turn, spawns portal entity on caster's tile when timer hits 0. Cancelled if caster dies.
- **Phase 0.8 (`_resolve_portal_tick`):** Decrements portal `turns_remaining` each turn (20 → 0), removes portal when expired
- **Phase 0.85 (`_resolve_extractions`):** Processes `INTERACT enter_portal` actions for heroes on the portal tile. Sets `player.extracted = True`. Also auto-extracts AI allies standing on portal tile.
- **Channel guards:** Channeling players blocked from movement, skills, ranged, and melee phases
- **Extracted guards:** Extracted players skip all resolution phases (movement, skills, ranged, melee)

**State model:**
- `MatchState.portal`: `{ active, x, y, turns_remaining, owner_id }` or `null`
- `MatchState.channeling`: `{ player_id, action, turns_remaining, tile_x, tile_y }` or `null`
- `PlayerState.extracted`: `bool` (default `False`)

**Tick Loop** (`server/app/services/tick_loop.py`):
- Persists channeling/portal state from `TurnResult` back to `MatchState` each tick
- Passes `match.portal` to AI decision engine
- Skips FOV, queues, auto-target, and actions for extracted players
- Broadcasts portal/channeling/extraction state in every `turn_result` payload

**Victory conditions** (dungeon mode only):
- `"dungeon_extract"` — all team_a heroes extracted or dead (at least one extracted)
- `"party_wipe"` — all team_a heroes dead, none extracted
- Normal team victory (kill all enemies) is suppressed in dungeon mode

**AI Portal Retreat** (`server/app/core/ai_stances.py`, `ai_behavior.py`):
- When a portal is active, hero AI allies override all stance behavior (except potion check)
- AI pathfinds to portal tile via A* (with door-opening support)
- On arrival, sends `INTERACT enter_portal` action
- If pathfinding fails (cornered), falls through to normal combat behavior
- Extracted AI units are skipped entirely in `run_ai_decisions`
- Portal state threaded: `tick_loop` → `run_ai_decisions()` → `decide_ai_action()` → `_decide_stance_action()`

### Client Implementation (Completed)

**Portal rendering** (`client/src/canvas/dungeonRenderer.js`):
- `drawPortal()` — animated purple radial gradient with two concentric rings, core dot, and turn counter
- `drawChanneling()` — progress bar above caster during 3-turn channel
- Drawn after tiles/ground items but before units in render pipeline

**Extracted heroes hidden** (`client/src/canvas/ArenaRenderer.js`):
- Units with `extracted: true` are skipped during rendering — they vanish when stepping through the portal

**Interaction system** (`client/src/hooks/useKeyboardShortcuts.js`):
- E-key Priority 0: portal extraction (highest priority, before loot/chest/door)
- Standing on active portal tile + press E → sends `INTERACT enter_portal`
- Extracted units are blocked from further interaction

**Portal HUD prompt** (`client/src/components/Arena/Arena.jsx`):
- Purple pulsing "↯ Enter Portal — Press E to escape" prompt appears when standing on the portal tile
- Styled in both `main.css` and `main-classic.css` with `portal-prompt` class and `portal-prompt-pulse` animation

**Auto-release control** (`client/src/context/reducers/combatReducer.js`):
- When the currently controlled unit gets extracted, control automatically switches to the next alive, non-extracted party member
- Prevents being stuck controlling a hero that has already left the dungeon

**Combat log** (`client/src/components/CombatLog/CombatLog.jsx`):
- Portal log type colored purple (`#cc66ff`) — extraction messages, portal spawn, portal expiry

**State management** (`client/src/context/reducers/combatReducer.js`):
- `portal` and `channeling` state updated from server payload each turn
- Extraction events logged to combat log
- Match end handles `dungeon_extract` and `party_wipe` winner types

### Files Modified (Backend)

- `server/app/core/turn_resolver.py` — 4 new portal phases, channeling/extraction logic, channel guards, extracted guards, portal constants
- `server/app/core/ai_stances.py` — portal retreat priority in `_decide_stance_action()`, pathfinding + INTERACT action generation
- `server/app/core/ai_behavior.py` — portal param on `decide_ai_action()` and `run_ai_decisions()`, extracted unit skip
- `server/app/services/tick_loop.py` — portal state persistence, passes portal to AI, extraction state in payloads
- `server/app/models/player.py` — `extracted: bool = False` field
- `server/app/models/actions.py` — portal-related fields on `TurnResult`
- `server/app/core/match_manager.py` — `extracted` included in player snapshot
- `server/app/core/hero_manager.py` — extracted heroes treated as survived (inventory persisted)

### Files Modified (Client)

- `client/src/canvas/ArenaRenderer.js` — extracted heroes skipped in render loop
- `client/src/canvas/dungeonRenderer.js` — `drawPortal()`, `drawChanneling()` functions
- `client/src/canvas/renderConstants.js` — portal color constants
- `client/src/hooks/useKeyboardShortcuts.js` — E-key portal extraction, extracted unit guard
- `client/src/components/Arena/Arena.jsx` — portal HUD prompt
- `client/src/components/CombatLog/CombatLog.jsx` — portal log color
- `client/src/context/reducers/combatReducer.js` — portal/channeling state, extraction logs, auto-release control
- `client/src/context/GameStateContext.jsx` — portal/channeling initial state
- `client/src/styles/main.css` — `.portal-prompt` styling + animation
- `client/src/styles/main-classic.css` — `.portal-prompt` styling + animation

---

## Feature 4: Multi-Floor Dungeon Progression ✅

**Status:** Implemented  
**Tests:** 1629/1629 full suite passing (zero regressions)

**Problem:** Dungeon runs are one flat floor. No escalation, no depth, no "how far can I push" tension.

**Goal:** Dungeons are now multi-floor runs (3–5 floors). Each floor is harder. Better loot drops deeper. Floor boss guards the stairs down.

**Result:** Party can now descend through unlimited procedurally generated floors. Stairs tile (`T`) unlocks when all enemies on the floor are dead. Pressing E on stairs takes the entire party to the next floor — new WFC-generated layout, scaled enemies, reset FOV. One-way trip, no backtracking.

### Progression Model (Implemented via `FloorConfig.from_floor_number()`)

| Floor | Grid Size | Enemy Types | Enemy Density | Loot Density |
|-------|-----------|-------------|---------------|---------------|
| 1–2 | 3×3 (18×18) | skeleton + demon boss | 60–65% | 30–32% |
| 3–4 | 4×4 (24×24) | demon + undead_knight boss | 70–80% | 34–38% |
| 5–6 | 5×5 (30×30) | wraith + undead_knight boss | 85–95% | 40–44% |
| 7–8 | 5×5 (30×30) | werewolf + reaper boss | 95–100% | 44–46% |
| 9+ | 6×6 (36×36) | construct + reaper boss | 100% | 46%+ |

### Floor Transition (Implemented)

- Each floor has a stairs tile (`T`), placed by `room_decorator.py` in boss/end rooms
- Stairs unlock automatically when all `team_b` enemies on the floor are dead
- Client shows "The stairs are blocked — defeat all enemies first!" if attempted while locked
- Pressing E on unlocked stairs sends `interact` with `target_id: 'enter_stairs'`
- Turn resolver validates position + unlock state in `_resolve_stairs()` (Phase 0.9)
- Tick loop calls `advance_floor()` which generates next WFC floor, respawns enemies, moves party to new spawn points, resets FOV/doors/chests/items, broadcasts full new floor state
- One-way trip — no backtracking (as designed)
- New floor = new procedurally generated layout via WFC (ties into Feature 5)

### Seed Chain (Deterministic)

```python
floor_seed = (base_seed + floor_number * 7919) & 0xFFFFFFFF
```
Same base seed always produces the same sequence of floors. Seed is stored in `MatchState.dungeon_seed`.

### Run Summary

- After extraction or party wipe, show a **run summary screen**: floors cleared, enemies killed, loot collected, gold earned, heroes lost
- This is the "dopamine receipt" — makes each run feel like an accomplishment
- *Not yet implemented — planned as a follow-up UI task*

### Files Modified (Server)

- `server/app/models/match.py` — `current_floor`, `dungeon_seed`, `stairs_unlocked` fields on MatchState
- `server/app/models/actions.py` — `floor_advance`, `new_floor_number` fields on TurnResult
- `server/app/core/turn_resolver.py` — `_resolve_stairs()` phase 0.9, stairs params on `resolve_turn()`
- `server/app/core/match_manager.py` — `get_stairs_info()`, `advance_floor()`, updated `_generate_procedural_dungeon()` and `get_match_start_payload()`
- `server/app/services/tick_loop.py` — stairs info passing to resolver, floor advance broadcast handling

### Files Modified (Client)

- `client/src/hooks/useKeyboardShortcuts.js` — E-key stairs interaction (Priority 0.5)
- `client/src/context/reducers/combatReducer.js` — `FLOOR_ADVANCE` case, `currentFloor`/`stairsUnlocked` state
- `client/src/App.jsx` — `floor_advance` WebSocket message handler
- `client/src/components/Arena/Arena.jsx` — stairs props to `useKeyboardShortcuts()`

### Architecture Reference

Modeled after the Portal Extraction system (Feature 3 / Phase 12C) — same pattern of `INTERACT` action with `target_id`, turn resolver validation phase, tick loop handling, and client E-key priority system.

---

## Feature 5: Procedural Dungeon Integration

**Problem:** The WFC Dungeon Lab and Cave Automata tools exist as standalone dev tools but don't feed into actual gameplay. Dungeon runs use handcrafted maps, so every run is identical.

**Goal:** Wire procedural generation into the match creation flow so each dungeon floor is unique.

### Approach

- When a dungeon match starts (or when descending to a new floor), the server generates a layout using WFC or cave automata instead of loading a static JSON map
- The existing WFC rulesets and module library define the building blocks — rooms, corridors, doors, chests, spawn points
- Each generated floor should place: rooms, corridors, doors, enemy spawn points, loot chests, a boss room, and a stairs-down tile
- Generation parameters scale with floor depth (more rooms, more enemy spawns, larger layout on deeper floors)
- Fallback: if generation fails (WFC contradiction), retry with a different seed or fall back to a handcrafted map

### Open Questions

- Server-side generation (Python) vs. pre-generate and cache?
- Port the JS WFC solver to Python, or call the existing JS tool as a subprocess?
- Minimum/maximum room counts per floor?
- How to ensure the boss room is always the deepest/farthest from spawn?

---

## Feature 6: Rare Item Tier & Loot Expansion

**Problem:** Only common and uncommon item rarities exist. For a dungeon crawler, the loot chase is the core motivator — 2 tiers isn't enough to sustain interest.

**Goal:** Add a Rare (blue) item tier with meaningfully stronger stats. Tie rarity to dungeon depth.

### New Rarity: Rare

- Stronger stat bonuses than uncommon
- Distinctive visual treatment (blue name/border, following the common=gray, uncommon=green convention)
- Drop from Floor 3+ enemies and chests, with low probability on Floor 2
- Boss guaranteed drops should include at least 1 rare on deeper floors

### Loot Expansion Ideas (pick during implementation)

- **Class-specific items** — weapons/armor that only certain classes can equip or that give class-relevant bonuses
- **Named uniques** — hand-crafted items with a special effect or flavor text (e.g., "Soulreaver — applies Wither on melee hit")
- **Consumable variety** — beyond health potions and portal scrolls: buff potions, antidotes, throwables
- **Epic tier** — if Rare feels natural, a 4th tier (purple) could follow in a future phase

### Merchant Integration

- The merchant's stock and prices should reflect the new tier
- Selling rares should give meaningful gold to fund the next run

---

## Feature 7: Mini-Map & Explored Tile Memory

**Problem:** Dungeon maps are 20x20+ with fog of war. Once you've explored a room and moved on, you lose visibility. Navigating back to find the stairs, a chest you skipped, or a retreating party member is frustrating.

**Goal:** Add a small mini-map overlay that remembers explored tiles.

### Behavior

- Small overlay in a corner of the game view (toggleable)
- Shows tiles the player/party has previously revealed, even if currently in fog
- Explored-but-not-visible tiles rendered in a muted/dimmed style
- Current party positions shown as dots
- Doors (open/closed state as last seen), stairs, and chests marked with simple icons
- Enemy positions shown only if currently visible (no memory of past enemy positions)

### Scope

- Pure client-side feature — the server already sends FOV data each tick
- Client tracks a "seen tiles" set that grows as the party explores
- Renderer draws the mini-map from this set

---

## Feature 8: Sound & Audio Foundation

**Problem:** The game is completely silent. Even minimal audio would dramatically improve the feel of combat and exploration.

**Goal:** Establish a basic audio system and add a first pass of essential sound effects. Not a full sound overhaul — just enough to make the game *feel alive*.

### Audio Categories

**Combat:**
- Melee hit (sword clang / thud)
- Ranged attack (arrow whoosh / bow twang)
- Skill cast (generic magic sound, can vary per skill type later)
- Death (enemy death groan, hero death sting)
- Damage taken (hit feedback)

**Dungeon Interaction:**
- Door open/close (creak)
- Chest open (latch + sparkle)
- Loot pickup (coin clink)
- Portal scroll activation (magic whoosh)

**Ambient:**
- Dungeon ambient loop (low droning, drips, distant echoes)
- Town ambient loop (tavern murmur, fire crackle)
- Combat music trigger (optional — when enemies are in FOV)

### Technical Approach

- Web Audio API or a lightweight library (Howler.js or similar)
- Audio manager singleton that the renderer/game state can call into
- Volume controls (master, SFX, ambient) — stored in local settings
- Assets: source royalty-free / CC0 sounds to start, can replace later

### Scope Limit

- This is a *foundation pass* — get the system in, get ~10-15 core sounds working
- Polish and variety (per-class skill sounds, per-enemy death sounds, etc.) is a later effort

---

## Implementation Order (Suggested)

The features have some natural dependencies. Suggested sequencing:

| Order | Feature | Rationale |
|-------|---------|-----------|
| **12A** | Feature 1 — Crusader & Ranger Skills | Quick win, unblocks CC system, immediate gameplay improvement |
| **12B** | Feature 2 — Crowd Control System | Builds on 12A skills, deepens combat before dungeon changes |
| **12C** | Feature 3 — Portal Scroll Extraction | Core loop mechanic, needed before multi-floor makes sense |
| **12D** | Feature 4 — Multi-Floor Progression | The big one — ties loot, difficulty, extraction together |
| **12E** | Feature 5 — Procedural Dungeon Integration | Makes 12D replayable — each run is unique |
| **12F** | Feature 6 — Rare Items & Loot Expansion | Rewards the loop — deeper floors drop better gear |
| **12G** | Feature 7 — Mini-Map | QoL that becomes essential with larger procedural dungeons |
| **12H** | Feature 8 — Sound Foundation | Polish pass — best done last when gameplay is stable |

Features 7 and 8 are independent and could be done at any point. Features 1-6 have a logical chain.

---

## Success Criteria

**Phase 12 is complete when:**

- All 5 classes have 4 skills each
- At least 3 CC types (stun, slow, root) are functional in combat
- Portal scroll extracts the party from a dungeon run
- A dungeon run spans 3+ floors with escalating difficulty
- Each floor is procedurally generated (no two runs identical)
- Rare item tier exists and drops on deeper floors
- Mini-map shows explored tiles and party positions
- Basic sound effects play during combat and exploration
- The town → dungeon → extraction → town loop is playable end-to-end
- Existing arena mode is completely unaffected (full backward compat)

---

## What Phase 12 is NOT

- **Not a content dump** — we're building systems, not hand-crafting 50 items or 20 maps
- **Not a rebalance** — current combat numbers are working; we add to them, not rework them
- **Not multiplayer networking overhaul** — same WebSocket architecture, same tick rate
- **Not visual overhaul** — canvas rendering stays, sprites stay; sound is the only sensory addition

---

## Post-Phase 12 Considerations

If the dungeon run loop feels complete after Phase 12, future phases could explore:

- **PvP encounters in dungeons** — other player parties as hostile encounters on the same floor
- **AoE abilities** — fireball, arrow rain, holy nova; depends on how CC and new skills feel
- **Elite/Champion enemy modifiers** — random affixes on enemies (e.g., "Regenerating," "Teleporting," "Armored")
- **Epic item tier** — 4th rarity with build-defining effects
- **Leaderboards / run history** — track best floor reached, fastest clears, most gold earned
- **Meta-progression** — town upgrades, unlockable classes, persistent bank improvements

---

**Document Version:** 1.3  
**Created:** February 2026  
**Last Updated:** Feature 3 — Portal scroll extraction mechanic fully implemented  
**Status:** In Progress — Features 1–3 Complete, Features 4–8 Planned  
**Prerequisites:** Phase 11 Complete (1495+ tests passing)
