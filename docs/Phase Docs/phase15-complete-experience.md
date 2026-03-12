# Phase 15 — The Complete Dungeon Experience

**Created:** February 28, 2026  
**Status:** Planning  
**Previous:** Phase 14D (Visual Feedback — Miss/Dodge/Blocked floaters) · 1,646+ tests passing · 0 failures  
**Timeframe:** ~1 month (4 weeks, ~10 sessions)

---

## Vision

Phase 15 transforms the Arena project from a strong single-player prototype into a **complete, replayable dungeon crawler with co-op multiplayer**. The work divides into three arcs:

1. **Weeks 1–2:** Close the loot loop & polish the feel — make the solo dungeon run genuinely fun to replay
2. **Weeks 3–4:** Co-op PvE foundation — 2–4 friends dungeon-crawling together

The original project vision is a **multiplayer roguelike with multifloor dungeons and PvPvE**. Phase 15 delivers the first two pillars; PvPvE becomes a natural follow-up once co-op infrastructure exists.

---

## Current Metrics (Phase Start)

| Metric | Value |
|--------|------:|
| Server Python (app/) | ~16,300 lines / 49 files |
| Server tests | ~22,500 lines / 45 files |
| Client JS/JSX | ~13,900 lines / 56 files |
| Client CSS (active) | ~8,300 lines / 27 files |
| Total (active) | ~61,000 lines / 152 files |
| Tests passing | 1,646+ |
| Test failures | 0 |
| Player classes | 5 |
| Skills | 24 |
| Enemy types | 22 (17 with skills) |
| Items | 19 (2 rarity tiers: common, uncommon) |
| Maps | 15 |
| Dungeon themes | 8 |
| Completed phases | 14 (through 14D) |

---

## Feature Summary

| # | Feature | Arc | Effort | Status |
|---|---------|-----|--------|--------|
| 15A | Rare Item Tier & Depth-Scaled Loot | Loot Loop | Medium | Planned |
| 15B | Elite/Champion Enemy Affixes | Loot Loop | Medium | Planned |
| 15C | Run Summary Screen | Loot Loop | Small–Medium | Planned |
| 15D | Audio Foundation | Polish | Medium | Planned |
| 15E | CC Visual Overlays & Hit Emphasis | Polish | Small | Planned |
| 15F | Minimap + Explored Tile Memory | Polish | Medium | Planned |
| 15G | Co-op Dungeon Lobby | Co-op | Medium | Planned |
| 15H | Shared Dungeon State & Loot Rules | Co-op | Medium | Planned |
| 15I | Co-op Difficulty Scaling | Co-op | Small–Medium | Planned |
| 15J | Co-op QoL (Chat, Pings, Summary) | Co-op | Small–Medium | Planned |

---

## Arc 1: Close the Loot Loop (Week 1)

### 15A — Rare Item Tier & Depth-Scaled Loot

**Problem:** Only 2 rarity tiers (Common, Uncommon) and 19 total items. The loot loop — the core motivator for repeated dungeon runs — has no real chase. Every floor drops the same pool regardless of depth.

**Goal:** Add a Rare (blue) tier with 10 items and wire depth-scaled drop rates so deeper floors reward risk.

#### New Rarity Tier

Add `RARE = "rare"` to the `Rarity` enum in `server/app/models/items.py`.

Client rarity color convention:
- Common = gray (`#aaaaaa`)
- Uncommon = green (`#44cc44`)
- Rare = blue (`#4488ff`)

#### New Items (10)

| item_id | Name | Slot | Rarity | Key Stats | Sell Value |
|---------|------|------|--------|-----------|------------|
| `rare_soulforged_blade` | Soulforged Blade | Weapon | Rare | +18 melee, +15 HP | 120 |
| `rare_bone_recurve` | Bone Recurve | Weapon | Rare | +20 ranged | 130 |
| `rare_doomhammer` | Doomhammer | Weapon | Rare | +24 melee, -2 armor | 140 |
| `rare_crusader_plate` | Crusader Plate | Armor | Rare | +12 armor, +20 HP | 150 |
| `rare_wraithcloak` | Wraithcloak | Armor | Rare | +8 armor, +40 HP | 140 |
| `rare_scale_of_the_deep` | Scale of the Deep | Armor | Rare | +14 armor | 160 |
| `rare_eye_of_inquisitor` | Eye of the Inquisitor | Accessory | Rare | +8 ranged, +20 HP | 130 |
| `rare_blood_signet` | Blood Signet | Accessory | Rare | +6 melee, +50 HP | 140 |
| `rare_bonelord_pendant` | Bonelord's Pendant | Accessory | Rare | +4 armor, +60 HP | 150 |
| `rare_elixir_of_wrath` | Elixir of Wrath | Consumable | Rare | Applies `war_cry` buff (3 turns) | 75 |

**Design notes:**
- Rare weapons are roughly 1.5–2× the stat budget of uncommon equivalents
- Rare armor/accessories combine two stat types (armor + HP, etc.) for build flexibility
- Doomhammer introduces a trade-off item (high melee, armor penalty) — first negative stat item
- Elixir of Wrath is the first non-heal consumable — uses existing `war_cry` buff effect, so no new skill code needed
- No class restrictions yet — any hero can equip any item (class-specific items deferred)

#### Depth-Scaled Drop Rates

Modify `server/app/core/loot.py` to accept an optional `floor_number` parameter. The loot roller adjusts pool weights based on depth:

| Floor | Common Weight | Uncommon Weight | Rare Weight | Boss Rare Guarantee |
|-------|--------------|-----------------|-------------|---------------------|
| 1–2 | 70% | 30% | 0% | No |
| 3 | 55% | 40% | 5% | No |
| 4 | 45% | 40% | 15% | No |
| 5–6 | 35% | 40% | 25% | Yes (1 item) |
| 7+ | 25% | 40% | 35% | Yes (1–2 items) |

**Implementation approach:**
- Add a `floor_bonus` multiplier to `roll_loot_table()` that shifts pool weights
- Boss loot tables get a `guaranteed_rarity: "rare"` field on deeper floors (mirrors existing `guaranteed_rarity: "uncommon"` pattern on Undead Knight)
- Chest loot tables gain floor-aware rare pools
- Merchant stock expanded: 1–2 rare items available for purchase at premium prices (300–500 gold)

#### Files Changed

| File | Changes |
|------|---------|
| `server/app/models/items.py` | Add `RARE = "rare"` to `Rarity` enum |
| `server/configs/items_config.json` | Add 10 rare item definitions |
| `server/configs/loot_tables.json` | Add rare item pools to enemy/chest tables, depth scaling config |
| `server/app/core/loot.py` | `floor_number` param on roll functions, depth-scaled weight adjustment |
| `server/app/core/turn_resolver.py` | Pass `current_floor` to loot roll calls (enemy death, chest interaction) |
| `server/configs/merchant_config.json` | Add 2–3 rare items to merchant stock with premium prices |
| `client/src/canvas/renderConstants.js` | Add rare color constant (`#4488ff`) |
| `client/src/styles/base/_variables.css` | Add `--rarity-rare` CSS variable |

#### Tests

- Rare items load from config and hydrate correctly
- `Rarity.RARE` enum works in all serialization paths
- Depth-scaled loot: floor 1 never drops rare, floor 5+ drops rare at expected rates (statistical)
- Boss guaranteed rare on floor 5+
- Rare items equip/unequip correctly, stat bonuses apply
- Elixir of Wrath consumable applies war_cry buff
- Merchant rare items buyable at correct prices
- Existing common/uncommon loot unchanged on floor 1–2 (backward compat)

---

### 15B — Elite/Champion Enemy Affixes

**Problem:** Deeper dungeon floors just have more HP/damage via stat scaling. There's no mechanical surprise — floor 7 is floor 1 but numbers are bigger. Enemies feel samey regardless of depth.

**Goal:** A random affix system that decorates enemies with 1–2 modifiers on deeper floors, creating mechanical variety and "oh no, a Regenerating Demon Lord" moments.

#### Affix Definitions

| Affix | Effect | Visual Indicator | Implementation |
|-------|--------|-----------------|----------------|
| **Regenerating** | Heals 5% max HP per turn | Green pulsing glow | `active_buffs` entry with `type: "regen"`, ticked in buff phase |
| **Frenzied** | +50% melee damage, -20% armor | Red pulsing aura | Modify stats at spawn, visual flag |
| **Shielded** | Starts with 3 ward charges | Blue shimmer ring | Apply `ward` buff at spawn (existing system) |
| **Venomous** | Melee attacks apply 1-turn wither | Purple tint | Check in melee phase, apply `wither` debuff (existing) |
| **Berserker** | +25% damage below 50% HP, +50% below 25% | Intensifying red glow | Check in damage calc, scale based on HP% |
| **Stalwart** | Immune to stun and slow | Iron/silver outline | Guard in CC application, skip stun/slow buffs |

#### Affix Scaling by Floor

| Floor | Affix Rules |
|-------|-------------|
| 1–2 | No affixes (baseline) |
| 3–4 | Elites/bosses get 1 random affix |
| 5–6 | All enemies get 1 affix, elites/bosses get 2 |
| 7+ | All enemies get 1–2 affixes, bosses get 2 |

#### Architecture

New module: `server/app/core/enemy_affixes.py`

```python
def apply_affixes(player_state: PlayerState, floor_number: int, rng: random.Random) -> list[str]:
    """Apply random affixes to an enemy based on floor depth.
    
    Modifies player_state in place (stats, active_buffs).
    Returns list of affix names applied.
    """
```

- Called during enemy spawning in `match_manager.py` / `room_decorator.py`
- Affix names stored on `PlayerState` in a new `affixes: list[str]` field
- Affixes sent to client in player snapshots for visual rendering
- Most affixes use existing mechanics (buffs, stat modification) — minimal new combat code
- **Regenerating** adds a new buff type `regen` to the buff tick system (counterpart to `wither`)
- **Venomous** hooks into melee damage resolution to apply wither (similar to how skills apply CC)
- **Berserker** hooks into damage calculation as a multiplier check

#### Client Rendering

- Affix visual indicators drawn as colored rings/glows around enemy units in `unitRenderer.js`
- Affix names shown in enemy tooltip/panel when targeting an enemy
- Combat log mentions affixes on first encounter: "A **Frenzied** Demon Lord approaches!"

#### Files Changed

| File | Changes |
|------|---------|
| `server/app/core/enemy_affixes.py` | **NEW** — affix definitions, `apply_affixes()`, stat/buff modifiers |
| `server/app/models/player.py` | Add `affixes: list[str] = []` field to PlayerState |
| `server/app/core/match_manager.py` | Call `apply_affixes()` during enemy spawning |
| `server/app/core/combat.py` | Berserker damage multiplier, Venomous wither-on-hit |
| `server/app/core/skills.py` | Stalwart CC immunity guard, Regen buff type in tick |
| `server/app/core/turn_resolver.py` | Regen tick in buff phase |
| `client/src/canvas/unitRenderer.js` | Affix visual indicators (colored rings/glows) |
| `client/src/components/EnemyPanel/` | Show affix names on targeted enemy |

#### Tests

- `apply_affixes()` returns empty list for floor 1–2
- Floor 3+ enemies receive expected affix count
- Regenerating heals 5% per turn, capped at max HP
- Frenzied modifies stats correctly (+50% melee, -20% armor)
- Shielded starts with 3 ward charges
- Venomous applies wither on melee hit
- Berserker damage scales with HP thresholds
- Stalwart immune to stun and slow
- Affixes appear in player snapshot
- Existing floor 1–2 enemies unchanged

---

### 15C — Run Summary Screen

**Problem:** When you extract from a dungeon or wipe, the game just ends. There's no "here's what you accomplished." This is the emotional payoff that motivates another run, and it's completely missing.

**Goal:** A post-dungeon-run summary showing key run statistics — the dopamine receipt.

#### Run Data Collection (Server)

Track cumulative stats during the match. New fields on `MatchState`:

```python
# Phase 15C: Run statistics
run_stats: dict = Field(default_factory=lambda: {
    "enemies_killed": 0,             # Total enemies killed
    "enemies_killed_by_type": {},     # {"demon": 3, "skeleton": 5, ...}
    "bosses_killed": 0,              # Boss enemies killed
    "floors_cleared": 0,             # Floors where all enemies were defeated
    "deepest_floor": 1,              # Highest floor number reached
    "chests_opened": 0,              # Total chests opened
    "doors_opened": 0,               # Total doors opened
    "total_damage_dealt": 0,         # Cumulative damage across all heroes
    "total_healing_done": 0,         # Cumulative healing across all heroes
    "gold_earned": 0,                # Total gold from loot sells / pickups
    "items_collected": 0,            # Total items picked up
    "rare_items_found": 0,           # Rare items specifically
    "potions_used": 0,               # Consumables used
    "turns_elapsed": 0,              # Total turns across all floors
    "heroes_extracted": [],          # Hero names that safely extracted
    "heroes_lost": [],               # Hero names that died (permadeath)
})
```

- Updated incrementally during turn resolution (death → enemies_killed++, chest → chests_opened++, etc.)
- `floors_cleared` increments when stairs unlock (all enemies dead on floor)
- `deepest_floor` updated on floor transition

#### Run Summary WS Message

When the match ends (extraction or party wipe), the server sends a `run_summary` message to all connected clients:

```json
{
  "type": "run_summary",
  "result": "extraction" | "party_wipe",
  "stats": {
    "enemies_killed": 23,
    "enemies_killed_by_type": {"demon": 5, "skeleton": 8, "necromancer": 1, "...": "..."},
    "bosses_killed": 2,
    "floors_cleared": 3,
    "deepest_floor": 4,
    "chests_opened": 6,
    "total_damage_dealt": 4820,
    "total_healing_done": 680,
    "gold_earned": 340,
    "items_collected": 12,
    "rare_items_found": 1,
    "potions_used": 5,
    "turns_elapsed": 87,
    "heroes_extracted": ["Sir Aldric", "Brother Cael"],
    "heroes_lost": ["Vex the Swift"]
  }
}
```

#### Client: RunSummaryScreen Component

New component: `client/src/components/PostMatch/RunSummaryScreen.jsx`

**Layout (grimdark themed):**
```
┌─────────────────────────────────────────┐
│         ☠ THE DUNGEON BECKONS ☠         │
│         Result: EXTRACTION / WIPE       │
│                                         │
│  ┌─ Heroes ──────────────────────────┐  │
│  │ ✓ Sir Aldric (Crusader) — Escaped │  │
│  │ ✓ Brother Cael (Confessor) — OK   │  │
│  │ ✗ Vex the Swift (Ranger) — DEAD   │  │
│  └────────────────────────────────────┘  │
│                                         │
│  ┌─ Dungeon ─────────────────────────┐  │
│  │ Deepest Floor:  4                 │  │
│  │ Floors Cleared: 3                 │  │
│  │ Turns Elapsed:  87                │  │
│  │ Enemies Slain:  23 (2 bosses)     │  │
│  │ Chests Opened:  6                 │  │
│  └────────────────────────────────────┘  │
│                                         │
│  ┌─ Plunder ─────────────────────────┐  │
│  │ Gold Earned:    340               │  │
│  │ Items Found:    12 (1 rare!)      │  │
│  │ Potions Used:   5                 │  │
│  └────────────────────────────────────┘  │
│                                         │
│  ┌─ Combat ──────────────────────────┐  │
│  │ Total Damage:   4,820             │  │
│  │ Total Healing:  680               │  │
│  └────────────────────────────────────┘  │
│                                         │
│         [ Return to Town ]              │
└─────────────────────────────────────────┘
```

- Shown instead of the generic `PostMatchScreen` when match type is `dungeon`
- "Return to Town" button navigates back to Town Hub screen
- Party wipe result uses red/darker styling; extraction uses gold/green
- Heroes listed with extraction/death status and class name
- Enemy kill breakdown expandable (click to see per-type counts)

#### Files Changed

| File | Changes |
|------|---------|
| `server/app/models/match.py` | Add `run_stats` field to MatchState |
| `server/app/core/turn_resolver.py` | Increment run_stats during resolution (kills, chests, healing, damage) |
| `server/app/services/tick_loop.py` | Send `run_summary` WS message on match end |
| `server/app/core/match_manager.py` | Include run_stats in floor advance, populate heroes_extracted/lost |
| `client/src/components/PostMatch/RunSummaryScreen.jsx` | **NEW** — run summary display |
| `client/src/context/reducers/combatReducer.js` | Handle `RUN_SUMMARY` action, store run stats |
| `client/src/App.jsx` | Route to RunSummaryScreen for dungeon matches, handle `run_summary` WS message |
| `client/src/styles/screens/_post-match.css` | Run summary styling |

#### Tests

- Run stats initialize to zeroes on match creation
- Enemy kill increments correctly (total + by type + boss flag)
- Chest/door open increments
- Floor clear and deepest floor tracking
- Heroes extracted/lost populated correctly on match end
- `run_summary` WS message sent on both extraction and party wipe
- Arena mode does not send run_summary (dungeon only)

---

## Arc 2: Polish & Feel (Week 2)

### 15D — Audio Foundation

**Problem:** The game is completely silent. This is the single biggest "feel" gap. Even 10–15 core sounds would dramatically improve the experience.

**Goal:** Establish a Web Audio API manager and add a first pass of essential sound effects using the existing `Assets/Audio/RPG Sound Pack/` assets.

#### AudioManager Architecture

New module: `client/src/audio/AudioManager.js`

```javascript
class AudioManager {
  constructor() {
    this.context = null;        // AudioContext (created on first user interaction)
    this.masterVolume = 0.7;
    this.sfxVolume = 1.0;
    this.ambientVolume = 0.4;
    this.buffers = {};          // Preloaded audio buffers by key
    this.ambientSource = null;  // Currently playing ambient loop
  }

  async init()                      // Create AudioContext, preload all SFX
  async preload(key, url)           // Fetch + decode a sound file into buffer cache
  play(key, options?)               // Play a one-shot SFX (volume, pitch variance)
  playAmbient(key)                  // Start looping ambient track
  stopAmbient()                     // Fade out + stop ambient
  setMasterVolume(v)                // 0–1
  setSfxVolume(v)                   // 0–1
  setAmbientVolume(v)               // 0–1
}
```

- Singleton instance exported as `audioManager`
- Initialized on first user click/keypress (browser autoplay policy)
- Volume settings persisted to `localStorage`

#### Core SFX Set (~15 sounds)

| Key | Event Trigger | Sound Description | Source |
|-----|---------------|-------------------|--------|
| `melee_hit` | Melee attack lands | Sword clash / blunt impact | RPG Sound Pack |
| `ranged_hit` | Ranged attack lands | Arrow thwip / impact | RPG Sound Pack |
| `ranged_miss` | Ranged miss / LOS blocked | Deflect / whiff | RPG Sound Pack |
| `heal` | Heal skill or potion used | Chime / warm glow | RPG Sound Pack |
| `buff_apply` | Buff applied (war cry, bulwark, etc.) | Ward hum / power-up | RPG Sound Pack |
| `skill_cast` | Generic skill activation | Arcane whoosh | RPG Sound Pack |
| `death` | Unit dies | Thud / collapse / death sting | RPG Sound Pack |
| `stun_hit` | Stun applied (shield bash) | Heavy metallic clang | RPG Sound Pack |
| `door_open` | Door opened | Creak | RPG Sound Pack |
| `chest_open` | Chest opened | Latch click + sparkle | RPG Sound Pack |
| `loot_pickup` | Item picked up from ground | Coin jingle | RPG Sound Pack |
| `portal_channel` | Portal scroll channeling starts | Hum build-up | RPG Sound Pack |
| `portal_open` | Portal materializes | Magic whoosh / pop | RPG Sound Pack |
| `wave_clear` | All enemies on floor/wave killed | Short fanfare sting | RPG Sound Pack |
| `floor_descend` | Descending to next floor | Descent rumble / stairs echo | RPG Sound Pack |

#### Ambient Tracks (2)

| Key | Context | Description |
|-----|---------|-------------|
| `dungeon_ambient` | Dungeon floors | Low drone, drips, distant echoes |
| `town_ambient` | Town Hub | Tavern murmur, fire crackle (if available) |

#### Integration Points

Wire `audioManager.play()` calls into existing event handlers:

| Trigger Location | When | Sound |
|------------------|------|-------|
| `combatReducer.js` → `TURN_RESULT` | Processing action results | `melee_hit`, `ranged_hit`, `ranged_miss`, `heal`, `death` |
| `combatReducer.js` → `TURN_RESULT` | Buff applied events | `buff_apply`, `stun_hit` |
| `combatReducer.js` → `TURN_RESULT` | Skill events | `skill_cast` |
| `App.jsx` → `door_changes` WS handler | Door opened | `door_open` |
| `App.jsx` → turn_result loot events | Chest opened / loot pickup | `chest_open`, `loot_pickup` |
| `App.jsx` → portal WS events | Channel start / portal open | `portal_channel`, `portal_open` |
| `App.jsx` → `floor_advance` handler | Floor transition | `floor_descend` |
| `App.jsx` → wave/stairs unlock | All enemies dead | `wave_clear` |
| `App.jsx` → screen transition | Enter town | `town_ambient` |
| `App.jsx` → match start | Enter dungeon | `dungeon_ambient` |

#### Volume Controls UI

Add a small volume panel accessible from the header bar or a settings gear icon:
- Master volume slider
- SFX volume slider  
- Ambient volume slider
- Mute toggle button

Settings stored in `localStorage` and loaded on init.

#### Files Changed

| File | Changes |
|------|---------|
| `client/src/audio/AudioManager.js` | **NEW** — Web Audio API manager, preloading, playback |
| `client/src/audio/soundMap.js` | **NEW** — mapping of sound keys to audio file paths |
| `client/src/App.jsx` | Init AudioManager on first interaction, wire ambient tracks to screen transitions |
| `client/src/context/reducers/combatReducer.js` | Trigger SFX on combat events in TURN_RESULT processing |
| `client/src/components/HeaderBar/` | Volume control UI (gear icon → dropdown with sliders) |
| `client/src/styles/components/_header-bar.css` | Volume control styling |

#### Non-Goals

- Per-class skill sounds (defer to future polish pass)
- Per-enemy death sounds (all enemies use same death SFX for now)
- Background music tracks (ambient loops only)
- Dynamic music system (combat music trigger — cool but complex, defer)

---

### 15E — CC Visual Overlays & Hit Emphasis

**Problem:** Stun and slow are invisible on the game canvas. The only indication is the combat log. When 8+ units are fighting, players can't tell which enemies are CC'd at a glance. Also, big hits look the same as small hits.

**Goal:** Add persistent visual overlays for CC states and emphasize critical/high-damage hits.

#### 15E-1: Stun Overlay

- **Visual:** Yellow-gold spinning stars (3 small stars rotating around the unit's head area)
- **Rendering:** New `drawStunOverlay(ctx, x, y, time)` in `unitRenderer.js`
- **Trigger:** Unit has `active_buffs` entry with `type: "stun"`
- **Animation:** Stars rotate at a constant angular speed, drawn above the unit shape

#### 15E-2: Slow Overlay

- **Visual:** Blue chain links / frost marks at the unit's feet
- **Rendering:** New `drawSlowOverlay(ctx, x, y, time)` in `unitRenderer.js`
- **Trigger:** Unit has `active_buffs` entry with `type: "slow"`
- **Animation:** Subtle pulsing frost/chain effect at unit base

#### 15E-3: Taunt Overlay

- **Visual:** Red aggro lines pointing from the taunted unit toward the taunt source
- **Rendering:** New `drawTauntOverlay(ctx, x, y, tauntSourceX, tauntSourceY)` in `unitRenderer.js`
- **Trigger:** Unit has `active_buffs` entry with `type: "taunt"`

#### 15E-4: Critical / Big Hit Emphasis

- **Threshold:** Any single hit dealing ≥30% of target's max HP
- **Visual:** Brief screen-edge flash (red vignette pulse, 200ms) + enlarged damage floater text + camera micro-shake (1–2 pixel offset for 150ms)
- **Rendering:** Flash overlay in `overlayRenderer.js`, enlarged floater in existing damage floater system
- **Overkill:** If damage exceeds remaining HP by 50%+, show "OVERKILL" text below the damage number

#### Files Changed

| File | Changes |
|------|---------|
| `client/src/canvas/unitRenderer.js` | `drawStunOverlay()`, `drawSlowOverlay()`, `drawTauntOverlay()` |
| `client/src/canvas/overlayRenderer.js` | Big hit screen flash, overkill text, micro-shake state |
| `client/src/canvas/ArenaRenderer.js` | Call CC overlays during unit render pass, apply shake offset |

#### Tests

- Visual verification (manual) — CC overlays display correctly on stunned/slowed/taunted units
- Overlays clear when buff expires
- Big hit emphasis triggers only above threshold
- No performance regression with overlay rendering

---

### 15F — Minimap + Explored Tile Memory

**Problem:** Procedural dungeon floors can be 24×24 to 36×36 tiles. Once you've explored a room and moved on, you lose visibility. Navigating back is frustrating.

**Goal:** Wire the existing `minimapRenderer.js` (281 lines, already in the codebase) into the dungeon flow with explored-tile memory.

#### Explored Tile Memory (Client-Side)

New state in game context:

```javascript
exploredTiles: new Set()  // Set of "x,y" strings — tiles ever revealed by FOV
```

- Updated each turn: merge current FOV visible tiles into `exploredTiles`
- Reset on floor transition (`FLOOR_ADVANCE` reducer)
- Persists for the duration of a single floor

#### Minimap Rendering

- **Position:** Top-right corner overlay, ~150×150px (toggleable with `M` key)
- **Expanded mode:** Click to expand to ~300×300px
- **Content:**
  - Explored tiles drawn in muted color (walls = dark gray, floors = dim)
  - Currently visible tiles drawn in brighter color
  - Party member dots (green)
  - Enemy dots (red, only if currently in FOV — no memory of past positions)
  - Door markers (yellow dot, open vs closed indicator)
  - Stairs marker (white, once discovered)
  - Portal marker (purple, if active)
  - Chest markers (gold dot, opened = dimmed)

#### Files Changed

| File | Changes |
|------|---------|
| `client/src/canvas/minimapRenderer.js` | Update to use `exploredTiles`, add door/stairs/portal markers |
| `client/src/canvas/ArenaRenderer.js` | Call minimap render in frame loop, pass explored tiles + game state |
| `client/src/context/reducers/combatReducer.js` | `exploredTiles` state, update on TURN_RESULT, reset on FLOOR_ADVANCE |
| `client/src/hooks/useKeyboardShortcuts.js` | `M` key toggle for minimap, click to expand |
| `client/src/styles/layout/_minimap.css` | Overlay positioning, expanded mode |

---

## Arc 3: Co-op PvE Foundation (Weeks 3–4)

### Architecture Assessment

The existing architecture is well-positioned for co-op. Key infrastructure already in place:

| Existing System | Co-op Readiness |
|----------------|-----------------|
| WebSocket per-player connections | ✅ Already handles multiple human players per match |
| Team system (team_a, team_b, etc.) | ✅ Multiple humans on same team works |
| Shared team FOV | ✅ All team_a members share vision |
| Party stance/control system | ✅ Works with multiple controlled units |
| Turn-based tick loop | ✅ Resolves all players simultaneously |
| Portal extraction (per-hero) | ✅ Individual extraction already designed for multi-hero |
| Loot system (ground items) | ✅ Items on ground, first-come-first-served by design |

What needs to change:

| Gap | Solution |
|-----|----------|
| Dungeon lobby assumes 1 human + AI party | Allow 2–4 humans, each picks 1 hero |
| AI ally system assumes 1 controller | Support multiple human controllers or reduce AI allies in co-op |
| Difficulty scaled for 1 human + 3 AI allies | Scale enemy count/stats for human player count |
| No in-dungeon communication | Add chat/ping system |
| Run summary is per-player perspective | Unified team summary with per-player contributions |

---

### 15G — Co-op Dungeon Lobby

**Problem:** The current dungeon lobby flow assumes a single human player who selects 1 hero and gets 3 AI party members. Multiple humans can technically join a match, but the dungeon hero selection and AI ally spawning don't account for it.

**Goal:** Allow 2–4 humans to join a dungeon match, each selecting their own hero. AI fills remaining party slots.

#### Lobby Flow Changes

**Current flow (solo):**
1. Host creates dungeon match
2. Host selects 1 hero from roster
3. Match starts → server spawns host's hero + 3 AI allies (4 total party)

**New flow (co-op):**
1. Host creates dungeon match, sets `max_players: 2–4`
2. Other players join via lobby browser (or invite code — future)
3. Each player selects 1 hero from their own roster
4. All players click "Ready"
5. Host clicks "Start" when all are ready
6. Match starts → server spawns all human heroes + AI fills remaining slots to 4 total

**Party composition:**

| Humans | AI Allies | Total Party |
|--------|-----------|-------------|
| 1 | 3 | 4 |
| 2 | 2 | 4 |
| 3 | 1 | 4 |
| 4 | 0 | 4 |

#### Server Changes

- `MatchConfig` gets `max_human_players: int = 1` for dungeons (separate from arena `max_players`)
- Hero selection: each human's `hero_select` WS message stores their chosen hero independently
- `start_match()` validates all humans have selected a hero before allowing start
- AI ally count = `4 - len(human_player_ids)` (configurable party size, default 4)
- Each human player gets `controlled_by: self` on their hero; AI allies get `controlled_by: None` (follow nearest human)

#### Client Changes

- Dungeon `WaitingRoom` shows player list with hero selection status
- Each player sees their own hero roster and selects independently
- "Ready" button per player
- Host sees "Start" button (grayed until all ready)
- Lobby chat available in waiting room (already exists for arena)

#### Control Model (Multi-Human Party)

In co-op, each human directly controls their own hero only. AI allies follow the **nearest alive human** using the existing stance system:

- AI `controlled_by` set to the nearest human on spawn
- If that human's hero dies/extracts, AI re-assigns to next nearest human
- Humans can still `set_party_control` to take manual control of an AI ally (one at a time)
- Stances work as-is: humans can set AI ally stances via the party panel

This means no changes to the combat/turn resolver — all existing systems handle multi-unit parties already.

#### Files Changed

| File | Changes |
|------|---------|
| `server/app/models/match.py` | `max_human_players` on MatchConfig |
| `server/app/core/match_manager.py` | Multi-human hero spawning, AI ally count based on humans, dynamic `controlled_by` |
| `server/app/services/message_handlers.py` | Per-player hero_select validation, ready-check for all humans |
| `server/app/routes/lobby.py` | Dungeon match creation with `max_human_players` param |
| `client/src/components/WaitingRoom/` | Multi-player ready status, per-player hero selection display |
| `client/src/components/Lobby/` | Dungeon match browser shows player count / slots |

---

### 15H — Shared Dungeon State & Loot Rules

**Problem:** With multiple humans in a dungeon, several systems need clarification: who gets loot, how does extraction work, what happens when one player disconnects?

**Goal:** Define and implement clear co-op rules for shared state.

#### Loot Rules

**Ground Items — First Come, First Served:**
- Items drop on the ground as normal
- Any player can walk to the tile and loot
- No automatic loot splitting — if you want it, pick it up
- This is simple, fair for a roguelike, and matches the existing system exactly

**Chest Items — Opener Gets:**
- The player who interacts with the chest receives the items in their inventory
- Other players see the chest is opened (already tracked in `chest_states`)
- No contention — chests are a reward for exploration

**Boss Drops — Enhanced for Co-op:**
- Boss enemies drop loot on the ground as normal
- In co-op (2+ humans), bosses drop `1 + human_count - 1` extra items (so 2 humans = 2 drops, 4 humans = 4 drops)
- Ensures everyone has a chance at boss loot without forced splitting

#### Extraction Rules

- Portal extraction remains **per-hero** (already designed this way in Phase 12C)
- Any human can use a portal scroll to open a portal
- All heroes (human and AI) can step through the portal independently
- A human who extracts sees the run summary immediately but can spectate remaining players (new: spectator state)
- Match ends when all team_a heroes are either extracted or dead

#### Disconnect Handling

- If a human disconnects mid-dungeon, their hero becomes AI-controlled (Follow stance toward nearest human)
- If they reconnect, they regain control
- If they don't reconnect and the match ends, their hero is treated as whatever state they're in (alive = extracted with loot, dead = permadeath)
- Existing `ConnectionManager.disconnect()` already tracks disconnections — extend with AI takeover

#### Spectator State

When a player's only hero extracts:
- They enter spectator mode — camera follows remaining human players
- Their inputs are disabled (no actions, no party control)
- They can toggle between following different human players
- They see the run summary when the match fully ends

#### Files Changed

| File | Changes |
|------|---------|
| `server/app/core/match_manager.py` | Boss loot scaling for co-op, disconnect → AI takeover |
| `server/app/core/loot.py` | `human_count` parameter for boss drop scaling |
| `server/app/services/websocket.py` | Disconnect handler → convert hero to AI, reconnect handler |
| `server/app/services/tick_loop.py` | Skip disconnected players in input processing (AI takes over) |
| `client/src/context/reducers/combatReducer.js` | Spectator state when own hero extracted |
| `client/src/components/Arena/Arena.jsx` | Spectator camera follow, disabled input overlay |

---

### 15I — Co-op Difficulty Scaling

**Problem:** Dungeon difficulty is calibrated for a party of 1 human + 3 AI allies. When 2–4 humans replace AI allies, the party is significantly stronger (humans make better tactical decisions). Dungeons would feel too easy.

**Goal:** Scale dungeon difficulty based on human player count.

#### Scaling Parameters

| Parameter | 1 Human | 2 Humans | 3 Humans | 4 Humans |
|-----------|---------|----------|----------|----------|
| Enemy HP multiplier | 1.0× | 1.15× | 1.3× | 1.5× |
| Enemy damage multiplier | 1.0× | 1.05× | 1.1× | 1.15× |
| Enemy count per room multiplier | 1.0× | 1.0× | 1.25× | 1.5× |
| Boss HP multiplier | 1.0× | 1.25× | 1.5× | 1.75× |
| Affix chance increase | — | +10% | +15% | +20% |
| Loot quantity bonus | 1.0× | 1.1× | 1.2× | 1.3× |

**Design notes:**
- HP scales faster than damage to make fights longer, not deadlier (avoid one-shots)
- Enemy count scaling only kicks in at 3+ humans to avoid overwhelming smaller parties
- Boss HP scales aggressively — bosses should feel like a team effort
- Loot quantity bonus compensates for more players sharing the loot pool
- All multipliers applied at spawn time via `FloorConfig` extension

#### Implementation

Extend `FloorConfig.from_floor_number()` to accept `human_count`:

```python
@classmethod
def from_floor_number(cls, floor_number: int, human_count: int = 1) -> "FloorConfig":
    config = cls._base_config(floor_number)
    config.enemy_hp_mult *= CO_OP_SCALING[human_count]["hp"]
    config.enemy_damage_mult *= CO_OP_SCALING[human_count]["damage"]
    # etc.
    return config
```

#### Files Changed

| File | Changes |
|------|---------|
| `server/app/core/match_manager.py` | Pass `human_count` to FloorConfig, apply scaling multipliers at spawn |
| `server/app/core/room_decorator.py` | Enemy count scaling based on human_count |

#### Tests

- Solo (1 human) produces baseline stats (no regression)
- 2-human scaling applies correct multipliers
- 4-human boss has 1.75× HP
- Enemy count rounding works correctly (1.25× of 3 = 4 enemies, not 3.75)

---

### 15J — Co-op QoL

**Problem:** Multiple humans in a shared dungeon need ways to communicate and coordinate beyond just watching each other move.

**Goal:** Add lightweight co-op communication tools.

#### 15J-1: In-Dungeon Chat

- Reuse the existing lobby chat infrastructure (`add_lobby_message`, `lobby_message` WS type)
- Rename/extend to a general `match_chat` system that works during gameplay
- Chat messages displayed in the combat log with a distinct color (white or cyan, distinct from combat events)
- Chat input: small text box at bottom of combat log, activated with Enter key
- Rate-limited to prevent spam (1 message per second)

#### 15J-2: Ping System

Quick tactical communication without typing:

| Ping Type | Key | Visual | Purpose |
|-----------|-----|--------|---------|
| **Alert** | `Alt+Click` on tile | Red ping marker, 3s decay | "Danger here" / "Look here" |
| **Gather** | `Ctrl+Click` on tile | Green ping marker, 3s decay | "Come here" / "Group up" |
| **Target** | `Ctrl+Click` on enemy | Gold ping marker on enemy, 3s | "Focus this enemy" |

- Pings sent as WS messages: `{ type: "ping", ping_type: "alert", x: 5, y: 8 }`
- Server broadcasts to all players in the match
- Client renders ping markers on canvas with fade-out animation
- Rate-limited (1 ping per 2 seconds per player)

**Note:** Pings are informational only — they don't issue commands to AI allies. That's a possible future enhancement.

#### 15J-3: Co-op Run Summary

Extend `RunSummaryScreen` from 15C to show per-player contributions:

```
┌─ Party Performance ────────────────────┐
│ Sir Aldric (Player1)                   │
│   Damage: 2,100  |  Healing: 0        │
│   Kills: 8       |  Items: 4          │
│                                        │
│ Brother Cael (Player2)                 │
│   Damage: 820    |  Healing: 680      │
│   Kills: 3       |  Items: 5          │
│                                        │
│ Ranger Bot (AI)                        │
│   Damage: 1,900  |  Healing: 0        │
│   Kills: 12      |  Items: 3          │
└────────────────────────────────────────┘
```

#### Files Changed

| File | Changes |
|------|---------|
| `server/app/services/message_handlers.py` | `match_chat` handler (extend lobby chat to in-match) |
| `server/app/services/websocket.py` | Broadcast `match_chat` to all players |
| `client/src/components/CombatLog/CombatLog.jsx` | Render chat messages, chat input box |
| `client/src/canvas/overlayRenderer.js` | Ping marker rendering with fade animation |
| `client/src/hooks/useCanvasInput.js` | Alt+Click / Ctrl+Click ping handlers |
| `client/src/components/PostMatch/RunSummaryScreen.jsx` | Per-player contribution breakdown |
| `server/app/models/match.py` | Per-player run stats in `run_stats` |

---

## Session-by-Session Schedule

| Session | Feature | Deliverable | Test Estimate |
|---------|---------|-------------|---------------|
| **1** | 15A — Rare Items | 10 rare items, depth-scaled loot, RARE enum, merchant integration | +30 tests |
| **2** | 15B — Enemy Affixes | 6 affixes, floor-scaled application, affix rendering | +25 tests |
| **3** | 15C — Run Summary | Server stat tracking, `run_summary` message, RunSummaryScreen UI | +15 tests |
| **4** | 15D — Audio Foundation | AudioManager, ~15 SFX, 2 ambient tracks, volume controls | +5 tests (mostly manual) |
| **5** | 15E — CC Overlays + Hits | Stun/slow/taunt overlays, big hit emphasis, overkill text | +5 tests (mostly visual) |
| **6** | 15F — Minimap Memory | Explored tiles, minimap overlay, door/stairs/portal markers | +5 tests (mostly visual) |
| **7** | 15G — Co-op Lobby | Multi-human dungeon lobby, per-player hero select, ready check | +25 tests |
| **8** | 15H — Shared State + Loot | Co-op loot rules, boss scaling, disconnect → AI, spectator | +20 tests |
| **9** | 15I — Difficulty Scaling | Human-count multipliers on enemy HP/damage/count | +15 tests |
| **10** | 15J — Co-op QoL | In-dungeon chat, ping system, co-op run summary | +10 tests |

**Projected test count at phase end:** ~1,800+ tests

---

## Dependencies & Ordering

```
                    ┌──── 15A (Rare Items) ◄────────────────────────┐
                    │                                                │
Week 1:    15A ──► 15B (Affixes, uses rare loot tables)             │
                    │                                                │
                    └──► 15C (Run Summary, references loot stats) ──┘
                    
Week 2:    15D (Audio) ──── independent ────
           15E (CC Overlays) ── independent ──
           15F (Minimap) ──── independent ────
           
                    ┌──── 15G (Co-op Lobby) ◄───────────────────────┐
                    │                                                │
Week 3-4:  15G ──► 15H (Shared State, needs lobby) ──► 15I (Scaling)│
                    │                                                │
                    └──► 15J (QoL, needs co-op infrastructure) ─────┘
```

- **15A must come first** — Rare items are referenced by affixes (Shielded affix) and run summary
- **15B depends on 15A** — affix loot scaling references rare drops
- **15C is semi-independent** — can be done in parallel with 15B but references loot stats
- **15D, 15E, 15F are fully independent** — can be done in any order
- **15G must come before 15H/15I/15J** — co-op lobby is the foundation
- **15H before 15I** — loot rules define what difficulty scaling compensates for
- **15J depends on 15G** — needs co-op infrastructure for chat/pings

---

## What This Sets Up (Post-Phase 15)

With Phase 15 complete, the natural next steps become:

| Feature | Why It's Now Possible |
|---------|----------------------|
| **PvPvE Dungeons** | Co-op infrastructure exists; add hostile team_b humans to the same floor |
| **Epic Item Tier (Purple)** | Rare items prove the system; add 4th tier with build-defining effects |
| **Class-Specific Items** | Item system supports it; add equip restrictions for deeper builds |
| **Town Meta-Progression** | Co-op creates gold sinks; add merchant upgrades, bank expansion, unlock tiers |
| **Leaderboards / Run History** | Run summary data is tracked; persist and rank it |
| **Additional Player Classes** | Co-op reveals role gaps (pure melee DPS, summoner, etc.) |
| **Dungeon Events / Traps** | Affix system proves runtime enemy modification; extend to environmental hazards |
| **Competitive PvPvE** | Two human parties in the same dungeon, racing + fighting for loot |

---

## What We're Intentionally NOT Doing

| Deferred Item | Rationale |
|---------------|-----------|
| Mana system | Cooldowns work well for roguelite pacing; mana adds complexity without clear gain right now |
| PvP in dungeons | Build co-op first, PvPvE naturally follows |
| Epic item tier | Rare needs to exist and breathe before adding a 4th tier |
| Additional classes (6th+) | 5 covers all archetypes; co-op will reveal if a gap exists |
| Performance monitoring | Not a bottleneck until co-op scale testing |
| Full sound overhaul | Foundation with ~15 SFX is the goal; per-class sounds are future polish |
| Ranged projectile travel (14G) | Cool visual but medium-large effort; defer until core co-op is stable |
| Structural file splits (13-4A-C) | Do opportunistically when touching those files, not as dedicated work |

---

## Success Criteria

**Phase 15 is complete when:**

- [ ] Rare (blue) item tier exists with 10 items and depth-scaled drop rates
- [ ] Elite/Champion affixes spawn on floor 3+ enemies with visual indicators
- [ ] Run summary screen shows comprehensive post-dungeon statistics
- [ ] Basic audio plays during combat, exploration, and town (15+ SFX)
- [ ] Stun, slow, and taunt have visible overlays on affected units
- [ ] Big hits get visual emphasis (flash + enlarged floater)
- [ ] Minimap shows explored tiles, party positions, doors, stairs
- [ ] 2–4 human players can join and play a dungeon run together
- [ ] Co-op loot rules work (first-come ground items, scaled boss drops)
- [ ] Difficulty scales with human player count
- [ ] In-dungeon chat and ping system functional
- [ ] Co-op run summary shows per-player contributions
- [ ] 1,800+ tests passing, 0 failures
- [ ] Existing solo dungeon and arena modes completely unaffected (full backward compat)

---

**Document Version:** 1.0  
**Created:** February 28, 2026  
**Status:** Planning  
**Prerequisites:** Phase 14D complete (1,646+ tests passing)
