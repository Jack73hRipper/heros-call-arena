# Phase 13 — Path Forward

**Created:** February 28, 2026  
**Status:** In Progress — Priority 1 Complete  
**Previous:** Phase 12C (Portal Scroll Extraction) complete · 1,641+ tests passing · 0 failures

---

## Where We Stand

The project is in excellent shape. 61,000+ lines across 152 files, a clean FastAPI + React architecture, 1,641 tests with zero failures, and 12 completed phases of features. The core game loop — lobby → town → dungeon → combat → extraction → town — is fully functional.

What we need now isn't more *systems*. It's more **depth in the systems we already have**, plus polish that makes everything feel alive.

---

## Priority 1 — Cleanup Pass (Quick Wins)

*Estimated effort: 1–2 sessions · Zero risk · Immediate satisfaction*

These are dead weight items identified in the codebase audit. Clearing them out reduces noise and makes the project feel tight.

### 1A. Dead File Purge (~13,300 lines)

| File | Lines | Why |
|------|------:|-----|
| `client/src/styles/main-monolith-backup.css` | 7,196 | Pre-split backup — the split is done and working |
| `client/src/styles/main-classic.css` | 2,553 | Old theme variant — superseded by CSS variables + ThemeEngine |
| `client/src/_archive/Arena.jsx.bak` | 1,167 | Pre-refactor backup — hooks extraction is stable |
| `client/src/_archive/ArenaRenderer.js.bak` | 1,380 | Pre-refactor backup — modular renderer is stable |
| `client/src/_archive/GameStateContext.jsx.bak` | 1,035 | Pre-refactor backup — sub-reducers are stable |
| `server/test_full_output.txt` | — | Stale test dump |
| `server/test_output.txt` | — | Stale test dump |
| `server/test_output2.txt` | — | Stale test dump |

### 1B. Remove Unused Dependency

- `socket.io-client` in `client/package.json` — the app uses native `WebSocket` via `useWebSocket.js`, not socket.io

### 1C. Deduplicate Shared Functions

| Function | Duplicated In | Action |
|----------|---------------|--------|
| `isInSkillRange()` | `BottomBar.jsx`, `HUD.jsx` | Extract to `client/src/utils/skillUtils.js` |
| `formatStatBonuses()` | `HeroDetailPanel.jsx`, `HeroRoster.jsx` | Extract to `client/src/utils/itemUtils.js` |

### 1D. Extract PostMatchScreen

- Currently ~200 lines embedded inline in `App.jsx`
- Move to `client/src/components/PostMatch/PostMatchScreen.jsx`

### 1E. Stale Config Cleanup

- Add `desktop.ini` to `.gitignore`
- Remove `server/package-lock.json` (empty Node lockfile in a Python project, if still present)

---

## Priority 2 — Content Depth (Variety Multipliers)

*The game has strong mechanics but thin content. These features make existing systems feel richer without building new engines.*

### 2A. Enemy Skill Expansion

**Problem:** 17 out of 22 enemy types are auto-attack-only stat bags. Only 6 enemies (Wraith, Medusa, Acolyte, Werewolf, Reaper, Construct) have skills. Bosses like Demon Lord, Necromancer, and Construct Guardian have huge HP pools but no abilities — they're just slow punching bags.

**Goal:** Give at least 8–10 more enemies a 1–2 skill kit using existing skill effects.

| Enemy | Suggested Skills | Rationale |
|-------|-----------------|-----------|
| Necromancer (Boss) | `wither`, `soul_reap` | Death mage fantasy — should be scariest caster |
| Demon Lord (Boss) | `war_cry`, `double_strike` | Overlord should buff and hit hard |
| Construct Guardian (Boss) | `ward`, `bulwark` | Arcane tank — should be nearly unkillable without focus |
| Undead Knight (Boss) | `shield_bash`, `bulwark` | Room guardian — should stun and wall up |
| Demon Knight (Elite) | `war_cry` | Armored demon commander buffs nearby |
| Imp Lord (Elite) | `war_cry` | Imp commander rallies swarm |
| Ghoul | `double_strike` | Fast undead — hit twice, feels frenzied |
| Skeleton | `evasion` or `crippling_shot` | Ranged sniper — dodge or slow pursuers |
| Undead Caster | `wither` | Skeleton mage applies DoTs |
| Horror (Elite) | `shadow_step`, `wither` | Aberration teleports and decays — terrifying |

**Files touched:** `server/configs/enemies_config.json` (add `class_id` entries), possibly `server/configs/skills_config.json` (new enemy-only skills if needed)

**Tests:** Add test cases for each new enemy skill interaction

### 2B. Rare Item Tier & Loot Expansion (Phase 12F)

**Problem:** Only 2 rarity tiers (Common, Uncommon) and 19 total items. The loot loop — the core motivator for repeated dungeon runs — has no real chase.

**Goal:** Add a Rare (blue) tier with 8–12 items and wire depth-scaled drop rates.

**New items (suggestion):**

| Slot | Item | Rarity | Notable Stat |
|------|------|--------|-------------|
| Weapon | Soulforged Blade | Rare | High melee + small HP bonus |
| Weapon | Bone Recurve | Rare | High ranged + vision bonus |
| Weapon | Doomhammer | Rare | Highest melee, slight armor penalty |
| Armor | Crusader Plate | Rare | High armor + HP |
| Armor | Wraithcloak | Rare | Moderate armor + vision bonus |
| Armor | Scale of the Deep | Rare | High armor + ranged reduction |
| Accessory | Eye of the Inquisitor | Rare | Vision + ranged bonus |
| Accessory | Blood Signet | Rare | Melee + HP |
| Accessory | Bonelord's Pendant | Rare | Armor + HP |
| Consumable | Elixir of Wrath | Rare | Temporary damage buff (new effect) |
| Consumable | Smoke Bomb | Rare | Temporary evasion charges (new effect) |

**Depth-scaled loot:**
- Floors 1–2: Common drops only
- Floors 3–4: Uncommon chance increases
- Floors 5+: Rare items enter the pool, chance scales with depth
- Boss chests on deeper floors guarantee Rare

**Files touched:** `items_config.json`, `loot_tables.json`, `server/app/core/loot.py`, loot-related tests

### 2C. Elite/Champion Affixes

**Problem:** Deeper dungeon floors just have more HP. There's no mechanical surprise.

**Goal:** A random affix system that decorates existing enemies with 1–2 modifiers on deeper floors.

**Suggested affixes:**

| Affix | Effect | Visual Indicator |
|-------|--------|-----------------|
| Regenerating | Heals 5% max HP per turn | Green glow |
| Frenzied | +50% melee damage, -20% armor | Red pulse |
| Shielded | Starts with 3 ward charges | Blue shimmer |
| Venomous | Attacks apply 1-turn wither | Purple tint |
| Berserker | Damage increases below 50% HP | Intensifying red |
| Stalwart | Cannot be stunned or slowed | Iron outline |

**Scaling:** Floor 1–2 = no affixes. Floor 3–4 = 1 affix on elites. Floor 5+ = 1–2 affixes on all enemies, bosses get 2.

**Architecture:** Single decorator function in a new `server/app/core/enemy_affixes.py` that modifies enemy stats and adds buff entries at spawn time. The existing buff/CC system handles the runtime effects.

---

## Priority 3 — Polish & Feel

### 3A. Sound Foundation (Phase 12H)

**Problem:** The game is completely silent. This is the single biggest "feel" gap.

**Goal:** Minimal viable audio — ~15 core sound effects + 1 ambient loop.

**Core SFX set:**

| Event | Sound |
|-------|-------|
| Melee hit | Sword clash / impact |
| Ranged hit | Arrow thwip |
| Ranged miss / LOS blocked | Deflect |
| Heal | Chime / glow |
| Buff applied | Ward hum |
| Skill use (generic) | Arcane whoosh |
| Death | Thud / collapse |
| Door open | Creak |
| Chest open | Latch click |
| Loot pickup | Coin jingle |
| Portal channel start | Hum build |
| Portal extract | Whoosh |
| Stun hit | Heavy clang |
| Wave clear | Fanfare sting |
| Level transition | Descent rumble |

**Architecture:** Web Audio API manager hooked into the turn result events. The `Assets/Audio/RPG Sound Pack/` folder already exists with assets.

**Files:** New `client/src/audio/AudioManager.js`, wire into `App.jsx` message handler alongside existing particle triggers.

### 3B. Run Summary Screen

**Problem:** When you extract from a dungeon or wipe, the game just... ends. No "here's what you accomplished."

**Goal:** Post-dungeon-run summary showing:
- Floors cleared
- Enemies defeated (by type)
- Loot acquired
- Gold earned
- Heroes extracted vs. lost (permadeath)
- Time spent
- Deepest floor reached

This is the "dopamine receipt" — the emotional payoff that makes you want to do another run.

**Architecture:** Server already tracks all this data during the match. Need a new `run_summary` WS message on match end, and a `RunSummary` component.

### 3C. Minimap & Explored Tile Memory (Phase 12G)

**Problem:** Procedural dungeon floors can be large. No way to see the big picture without scrolling around.

**Goal:** Corner overlay minimap showing:
- Explored tiles (persisted for the floor)
- Party positions
- Door locations
- Stairs/portal location once discovered

**Note:** A `minimapRenderer.js` (281 lines) already exists in the canvas pipeline. This is about wiring it into the dungeon flow with explored-tile memory.

---

## Priority 4 — Structural Health

*Not urgent, but pays dividends before adding more features.*

### 4A. Split match_manager.py

The Feb 2026 audit flagged this at 1,388+ lines with 51 functions and 7+ responsibilities. Recommended split:

| New Module | Responsibility |
|-----------|---------------|
| `match_lifecycle.py` | Create, start, end, cleanup |
| `match_spawning.py` | Player/AI/enemy spawning, wave management |
| `match_fov.py` | FOV computation, team vision merging |
| `match_state.py` | State queries, player lookups, tile checks |

### 4B. Split skills.py

At 1,447+ lines with config loading + buff queries + 17 effect resolvers. Recommended split:

| New Module | Responsibility |
|-----------|---------------|
| `skills_config.py` | Config loading, validation |
| `skills_effects.py` | All 17+ effect resolver functions |
| `skills_buffs.py` | Buff queries, duration checks, stacking |

### 4C. Client Large File Splits

| File | Lines | Suggested Split |
|------|------:|-----------------|
| `pathfinding.js` | 807 | `aStar.js`, `smartActions.js`, `groupMovement.js` |
| `BottomBar.jsx` | 741 | Extract `SkillBar`, `PotionSlot`, `IntentBanner` sub-components |
| `HeroDetailPanel.jsx` | 619 | Extract `EquipmentSlots`, `BagGrid`, `TransferModal` |

---

## Suggested Order of Attack

```
Session 1:  Priority 1 — Cleanup Pass (all of 1A through 1E)
Session 2:  Priority 2A — Enemy Skill Expansion (config-driven, fast)
Session 3:  Priority 2B — Rare Item Tier + Depth-Scaled Loot
Session 4:  Priority 3B — Run Summary Screen
Session 5:  Priority 2C — Elite/Champion Affixes
Session 6:  Priority 3A — Sound Foundation
Session 7:  Priority 3C — Minimap + Explored Memory
Session 8+: Priority 4 — Structural splits as needed
```

Each session is self-contained — you can stop after any one and the project is in a better state than before.

---

## Post-Phase 13 Horizon (Ideas Parking Lot)

These are interesting but not yet committed:

- **Mana system** — The `mana_cost` field exists on all 24 skills (always 0). Could add resource management, but cooldown-only works well for roguelite pacing. Defer unless the game starts feeling too spammy.
- **PvP dungeon encounters** — Other player parties as hostile encounters mid-dungeon. Massive replay value, significant networking complexity.
- **Epic item tier** — 4th rarity (purple), build-defining effects (procs, on-hit, set bonuses). Needs Rare tier to exist first.
- **Class-specific items** — Items only certain classes can equip. Adds build identity.
- **Additional player classes** — 6th+ class. The 5-class roster covers tank/support/scout/ranged/hybrid well, but a pure melee DPS or summoner archetype would fill gaps.
- **Town upgrades / meta-progression** — Spend gold to upgrade merchant stock, unlock new hiring hall tiers, expand bank. Gives gold a long-term sink.
- **Leaderboards / run history** — Track best runs, deepest floors, fastest clears.
- **Performance monitoring** — Server tick timing, FOV computation cost, AI decision time. Deferred since Phase 3.

---

## Metrics at Phase Start

| Metric | Value |
|--------|------:|
| Server Python (app/) | ~16,300 lines / 49 files |
| Server tests | ~22,500 lines / 45 files |
| Client JS/JSX | ~13,900 lines / 56 files |
| Client CSS (active) | ~8,300 lines / 27 files |
| Total (active) | ~61,000 lines / 152 files |
| Tests passing | 1,641+ |
| Test failures | 0 |
| Player classes | 5 |
| Skills | 24 |
| Enemy types | 22 (17 with skills) |
| Items | 19 (2 rarity tiers) |
| Maps | 15 |
| Dungeon themes | 8 |
| Completed phases | 12 (A through C in Phase 12) |

---

## Implementation Log

### Priority 1 — Cleanup Pass (February 28, 2026)

**1A. Dead File Purge — COMPLETE**
Deleted 8 files:
- `client/src/styles/main-monolith-backup.css` (7,196 lines) — pre-split CSS backup
- `client/src/styles/main-classic.css` (2,553 lines) — old theme variant
- `client/src/_archive/Arena.jsx.bak` (1,167 lines) — pre-refactor backup
- `client/src/_archive/ArenaRenderer.js.bak` (1,380 lines) — pre-refactor backup
- `client/src/_archive/GameStateContext.jsx.bak` (1,035 lines) — pre-refactor backup
- `server/test_full_output.txt` — stale test dump
- `server/test_output.txt` — stale test dump
- `server/test_output2.txt` — stale test dump

Also removed `main-classic.css` reference from README and backup comment from `main.css`.

**1B. Remove Unused Dependency — COMPLETE**
- Removed `socket.io-client` from `client/package.json` dependencies (app uses native WebSocket)

**1C. Deduplicate Shared Functions — COMPLETE**
- Created `client/src/utils/skillUtils.js` — extracted `isInSkillRange()` from BottomBar.jsx and HUD.jsx
- Created `client/src/utils/itemUtils.js` — extracted `formatStatBonuses()` from HeroDetailPanel.jsx, HeroRoster.jsx, Bank.jsx, and Inventory.jsx (4 copies, not 2 as originally listed)
- All 6 consumer files updated to import from shared utils
- Standardized stat label format across all consumers (Inventory previously used "Melee Dmg"/"Max HP" vs others' "Melee"/"HP")

**1D. Extract PostMatchScreen — COMPLETE**
- Created `client/src/components/PostMatch/PostMatchScreen.jsx` (215 lines)
- Removed inline `PostMatchScreen` function from App.jsx (614 → 399 lines)
- Added PostMatchScreen import, removed unused `useMemo` and `HeroSprite` imports from App.jsx

**1E. Stale Config Cleanup — COMPLETE**
- Added `desktop.ini` to `.gitignore`
- Deleted `server/package-lock.json` (empty Node lockfile in Python project)

**Verification:** 1,641 tests passing, 0 failures (no regressions)

### Priority 2A — Enemy Skill Expansion (February 28, 2026)

**Problem:** 17 out of 22 enemy types were auto-attack-only stat bags. Only 6 enemies had skills. All 5 bosses except the Reaper had zero abilities — massive HP pools with no mechanical identity.

**Goal:** Give 11 more enemies a 1–2 skill kit using existing skill effects. No new skills needed.

**Approach:** Assigned each enemy a role archetype and matched 1–2 existing skills to its fantasy and stat profile. Added `class_id` entries to enemies_config, wired skills in skills_config `class_skills` + `allowed_classes`, and registered AI roles in `_CLASS_ROLE_MAP`.

#### Bosses (4 enemies — all bosses now have abilities)

| Enemy | class_id | Skills | AI Role | Combat Impact |
|-------|----------|--------|---------|---------------|
| Necromancer (380hp, 16 ranged) | `necromancer` | `wither`, `soul_reap` | hybrid_dps | Death mage: Wither DoT (24 armor-bypass) + Soul Reap burst (32 dmg). Scariest ranged caster boss. |
| Demon Lord (480hp, 28 melee) | `demon_lord` | `war_cry`, `double_strike` | tank | Overlord: War Cry → 56 dmg melee hits. Double Strike = 33.6 burst. Absolute freight train. |
| Construct Guardian (550hp, 14 armor) | `construct_guardian` | `ward`, `bulwark` | tank | Arcane wall: Ward reflects 24 total + Bulwark → 22 armor. Nearly unkillable without DoTs. |
| Undead Knight (425hp, 12 armor) | `undead_knight` | `shield_bash`, `bulwark` | tank | Room guardian: Shield Bash = 17.5 + stun. Bulwark → 20 armor. Locks targets down. |

#### Elites (3 enemies)

| Enemy | class_id | Skills | AI Role | Combat Impact |
|-------|----------|--------|---------|---------------|
| Demon Knight (260hp, 8 armor) | `demon_knight` | `war_cry` | tank | Armored commander: War Cry → 40 dmg melee hits. |
| Imp Lord (180hp, 16 melee) | `imp_lord` | `war_cry` | tank | Imp chieftain rallies: War Cry → 32 melee. Scary for mid-tier. |
| Horror (240hp, 18 melee) | `horror` | `shadow_step`, `wither` | hybrid_dps | Aberration: Teleports in and applies 24 armor-bypass DoT. Terrifying. |

#### Fodder/Mid (4 enemies)

| Enemy | class_id | Skills | AI Role | Combat Impact |
|-------|----------|--------|---------|---------------|
| Ghoul (100hp, 14 melee) | `ghoul` | `double_strike` | tank | Frenzied undead: DS = 2×8.4 = 16.8 burst. Glass cannon melee. |
| Skeleton (125hp, 14 ranged) | `skeleton` | `evasion` | ranged_dps | Ranged sniper: Dodges 2 incoming attacks. Annoying to trade with at range. |
| Undead Caster (120hp, 16 ranged) | `undead_caster` | `wither` | hybrid_dps | Skeleton mage: Adds 24 armor-bypass DoT to ranged output. |
| Shade (130hp, 14 melee) | `shade` | `shadow_step` | hybrid_dps | Shadow creature: Teleports to strike from unexpected angles. |

#### Intentionally Left Skill-less (5 enemies)

| Enemy | Rationale |
|-------|-----------|
| Demon (240hp) | Base melee beatstick. Demon Knight is the upgraded version with abilities. |
| Imp (70hp) | Swarm fodder in groups of 4–6. Skills would slow AI processing. |
| Insectoid (80hp) | Swarm fodder. Simple by design. |
| Goblin Spearman (90hp) | Basic humanoid fodder. |
| Evil Snail (60hp) | Novelty enemy. Its charm is being a dumb armored gastropod. |

**Files changed:**
- `server/configs/enemies_config.json` — added `class_id` to 11 enemies, updated descriptions
- `server/configs/skills_config.json` — added 11 new `class_skills` entries, expanded `allowed_classes` on 9 skills
- `server/app/core/ai_skills.py` — added 11 entries to `_CLASS_ROLE_MAP` (11 → 22 total)
- `server/tests/test_ai_skills.py` — updated role map count assertion (11 → 22)
- `server/tests/test_enemy_types.py` — updated boss AI test to accept SKILL actions
- `server/tests/test_skills.py` — updated 3 skill definition tests to use `in` checks for expanded allowed_classes

**Result:** 17/22 enemies now have skills (was 6/22). All 5 bosses have abilities. 0 new skill types created — all assignments reuse existing effects.

**Verification:** 1,641 tests passing, 0 failures (no regressions)