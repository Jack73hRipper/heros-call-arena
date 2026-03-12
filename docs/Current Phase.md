Current Phase

## Current Phase

**Arena Analyst Phase D — Advanced Views** (Complete — D1: Composition Analysis with ranked best/worst comps + sortable/filterable comp table; D2: Timeline Replay with SVG damage curves + turn-by-turn event scrubber + death markers + event type filters; D3: Trend Charts with summary cards + match volume bars + avg match length line chart + damage creep chart + stacked win rate distribution + class win rate overview)

**WFC Integration Phase C — Shared Module Format** (Complete — Canonical library.json format v2; server loads from JSON with hardcoded builtin fallback; WFC tool exports library to server via API + download; tool imports library JSON for round-trip; 38 tests)

**WFC Integration Phase B — Batch Generation** (Complete — Best-of-N candidate selection with quality scoring: floor ratio + spawn presence + natural connectivity; batch_size=3 default, per-FloorConfig override; 33 tests)

**WFC Integration Phase A — Dungeon Style Templates** (Complete — 5 styles: balanced, dense_catacomb, open_ruins, boss_rush, treasure_vault; weight overrides + decorator overrides; floor-based auto-selection; 51 tests)

**Phase 18E — Client Visual Feedback** (Complete — E1–E12: name colors, rarity glow, champion tints, ghostly alpha, affix ambient particles, minimap colors, combat log colors, enemy panel, on-death explosions, death celebrations, preset JSON files)

**Phase 18I — Enemy Identity Skills** (Complete — 5 new skills: Demon Enrage, Skeleton Bone Shield, Imp Frenzy Aura, Dark Priest Dark Pact, Acolyte Profane Ward; new effect types: passive_enrage, damage_absorb, tag-filtered passive aura; 42 tests)

**Phase 18H — Enemy Forge Tool** (Complete — Standalone Vite + React + Express dev tool with 8 tabs: Enemy Browser/Editor, Affix Editor, Champion Type Editor, Floor Roster Viewer, TTK Simulator, Spawn Preview, Super Unique Editor, Export Panel with diff + backup)

**Phase 18G — Super Uniques** (Complete — 4 hand-crafted bosses: Malgris the Defiler, Serelith Bonequeen, Gorvek Ironhide, The Hollow King; fixed affixes, retinues, unique loot tables; floor-based spawn chance; 63 tests)

**Phase 18D — Combat Integration** (Complete — Aura resolution, on-hit effects, on-death explosions, ghostly phase-through, teleporter auto-cast, minion unlinking, 33 tests)

**Phase 18C — Spawn Integration** (Complete — Rarity rolling in dungeon/wave spawns, champion packs, rare minions, BFS tile placement, WebSocket broadcast, 28 tests)

**Phase 18B — Affix Engine** (Complete — Rarity rolling, affix selection, name generation, stat application, minion creation, 150 tests)

**Phase 18A — Monster Rarity Data Model** (Complete — Config, models, validation, 79 tests)

**Phase 16A — Stat Expansion** (Complete — Foundation for Diablo-style item overhaul)

**Phase 16E — Set Items** (Complete — 5 sets, 15 pieces, tiered set bonuses, skill modifiers)

**Combat Meter** — Live combat statistics panel (In Progress)

**Phase 10G — Skill & Ability Auto-Target Pursuit** (Complete — 10G-1 through 10G-8)

**Phase 8K — AI Retreat Behavior & Kiting** (Complete — 8K-1 through 8K-4)

**Wave Arena — AI Testing Map** (Complete)

| Area | Status |
|------|--------|
| **Combat Meter — Live Stats Panel** | |
| combatStatsReducer (client-side stat accumulation from turn_result) | ✅ Complete |
| GameStateContext integration (CombatStatsContext, hooks) | ✅ Complete |
| CombatMeter panel component (dropdown selector, views) | ✅ Complete |
| DamageDoneView (sorted bar chart with DPT) | ✅ Complete |
| DamageTakenView (tank metric bars) | ✅ Complete |
| HealingDoneView (healer output bars) | ✅ Complete |
| KillsView (kill leaderboard table) | ✅ Complete |
| OverviewView (full stats table) | ✅ Complete |
| BottomBar toggle button (⚔ icon) | ✅ Complete |
| Tab hotkey toggle | ✅ Complete |
| CSS styling (grim dark theme, animations) | ✅ Complete |
| Per-skill breakdown view | 🟨 Not started |
| Team grouping in PvP | 🟨 Not started |
| Mini-meter inline on action bar | 🟨 Not started |
| Overkill / damage mitigated tracking | 🟨 Not started (needs server addition) |
| Buff uptime tracking | 🟨 Not started |
| Kill participation / assists | 🟨 Not started |
| **Phase 2 (complete)** | |
| New Maps (4 total) | ✅ Complete |
| FOV / Fog of War | ✅ Complete |
| Ranged Attacks + Cooldowns | ✅ Complete |
| AI Behavior + A* Pathfinding | ✅ Complete |
| Match Types (PvP/PvE/Mixed) | ✅ Complete |
| Team System (4 teams) | ✅ Complete |
| Frontend (Lobby, HUD, HeaderBar, BottomBar, Arena, CombatLog) | ✅ Complete |
| Bug Fixes #1–#8 | ✅ All Fixed |
| Lobby Chat | ✅ Complete |
| **Phase 3: Week 1 — Larger Map Variants** | |
| Open Arena Small (12×12) | ✅ Complete |
| Open Arena Large (20×20) | ✅ Complete |
| Maze Large (20×20) | ✅ Complete |
| Islands Large (20×20) | ✅ Complete |
| Test Map XL (25×25) | ✅ Complete |
| Lobby map selector with size labels | ✅ Complete |
| Variable grid size support | ✅ Complete |
| **Phase 3: Week 2 — Smart Spawn System** | |
| Team-based spawning | ✅ Complete |
| FFA spawning (max distance) | ✅ Complete |
| Spawn validation | ✅ Complete |
| Map spawn zone configs | ✅ Complete |
| **Phase 3: Week 3 — Performance Monitoring** | |
| Client FPS / latency overlay | 🟨 Deferred to Phase 5 |
| Server tick/FOV/AI timing logs | 🟨 Deferred to Phase 5 |
| **Phase 4A: Class System Foundation** | |
| Class config (5 classes) | ✅ Complete |
| Server model (ClassDefinition, class_id on PlayerState) | ✅ Complete |
| Combat uses per-class stats (HP, damage, armor, range) | ✅ Complete |
| Class selection in lobby (WS + UI) | ✅ Complete |
| AI spawns with random classes | ✅ Complete |
| Class-based rendering (colors + shapes) | ✅ Complete |
| HUD shows class info | ✅ Complete |
| REST endpoint for class list | ✅ Complete |
| Backward compat (class_id=null works) | ✅ 164 tests pass |
| **Phase 4B-1: Dungeon Map Format & Server Foundation** | |
| Dungeon test map (20×20, 5 rooms, tile grid) | ✅ Complete |
| Map loader extension (doors, chests, rooms, tiles) | ✅ Complete |
| Tile-grid obstacle generation for dungeon maps | ✅ Complete |
| Model scaffolding (INTERACT, LOOT, DUNGEON enums) | ✅ Complete |
| Door/chest state dicts on MatchState | ✅ Complete |
| Dungeon match creation + state init | ✅ Complete |
| Arena backward compat (no regression) | ✅ 228 tests pass |
| Lobby UI dungeon map option | ✅ Complete (moved to 4B-2) |
| **Phase 4B-2: Door Mechanics, FOV & Dungeon Rendering** | |
| Door interaction (INTERACT opens/closes doors) | ✅ Complete |
| FOV respects door state (closed=wall, open=floor) | ✅ Complete |
| Movement blocked by closed doors, allowed through open | ✅ Complete |
| Ranged LOS blocked by closed doors | ✅ Complete |
| Dungeon tile renderer (walls, floors, doors, chests) | ✅ Complete |
| Viewport snap-scroll auto-center on player | ✅ Complete |
| Interact button + interact action mode | ✅ Complete |
| Door/chest state tracking in GameState | ✅ Complete |
| Dungeon map + match type in lobby dropdowns | ✅ Complete |
| WebSocket broadcasts door_changes/door_states | ✅ Complete |
| Arena backward compat (no regression) | ✅ 268 tests pass |
| **Phase 4C: Enemy Types & Enhanced AI** | |
| Enemy config (3 types: Demon, Skeleton, Undead Knight) | ✅ Complete |
| EnemyDefinition model + apply_enemy_stats | ✅ Complete |
| Dungeon enemy spawning (2 per room, 1 boss) | ✅ Complete |
| AI behavior profiles (aggressive, ranged, boss) | ✅ Complete |
| Room leashing (enemies stay in assigned rooms) | ✅ Complete |
| Ranged AI kiting + retreat behavior | ✅ Complete |
| Boss AI room guardian (never leaves room) | ✅ Complete |
| Enemy visuals (colors, shapes, boss glow) | ✅ Complete |
| Combat log enhancements (boss_kill, enemy_spawn) | ✅ Complete |
| Server payloads include enemy_type fields | ✅ Complete |
| Arena backward compat (no regression) | ✅ 311 tests pass |
| **Phase 4D-1: Item Models, Configs & Loot Generation** | |
| Item model (Item, StatBonuses, Equipment, Inventory) | ✅ Complete |
| Items config (18 items, 4 types, 2 rarities) | ✅ Complete |
| Loot tables config (3 enemy + 2 chest tables) | ✅ Complete |
| Loot generation utility (roll_enemy_loot, roll_chest_loot) | ✅ Complete |
| PlayerState equipment/inventory scaffolding | ✅ Complete |
| Arena backward compat (no regression) | ✅ 398 tests pass |
| **Phase 4D-2: Equipment, Loot Drops & Consumables** | |
| Equipment bonuses in combat (weapon/armor/accessory) | ✅ Complete |
| Ground items tracking on MatchState | ✅ Complete |
| Enemy death → loot drops on ground | ✅ Complete |
| Chest interaction (LOOT action generates items) | ✅ Complete |
| Ground item pickup (LOOT action on tile) | ✅ Complete |
| Inventory cap enforcement (overflow to ground) | ✅ Complete |
| Equip/unequip via WS messages | ✅ Complete |
| Health Potion USE_ITEM (heal, consume, cap at max_hp) | ✅ Complete |
| Portal Scroll stored but deferred to 4F | ✅ Complete |
| WS broadcast: loot events, inventory, equipment | ✅ Complete |
| Arena backward compat (no regression) | ✅ 446 tests pass |
| **Phase 4D-3: Client Inventory UI & Ground Item Rendering** | |
| Inventory panel (3 equip slots + 10-slot bag grid) | ✅ Complete |
| Click equip/unequip/use sends correct WS messages | ✅ Complete |
| Item tooltips (name, rarity, stats, description, sell value) | ✅ Complete |
| Ground item sparkle rendering (pulsing glow + count) | ✅ Complete |
| Loot highlight on player's tile + prompt | ✅ Complete |
| 🎒 Loot button (ground items + adjacent chest) | ✅ Complete |
| 🧪 Potion quick-use button with count | ✅ Complete |
| Queue display for loot/use_item actions | ✅ Complete |
| HUD equipment summary + bag count + potion count | ✅ Complete |
| Rarity color system (common=gray, uncommon=green) | ✅ Complete |
| Combat log loot/heal entries | ✅ Complete |
| Arena mode completely unaffected | ✅ 446 tests pass |
| **Phase 4E-1: Hero Models, Persistence & Town REST API** | |
| PlayerProfile & Hero models | ✅ Complete |
| JSON file persistence (save/load/create) | ✅ Complete |
| Hero generation with stat variation | ✅ Complete |
| Name generator config (curated per class) | ✅ Complete |
| Town REST endpoints (profile, tavern, hire, roster) | ✅ Complete |
| Mount town router in main.py | ✅ Complete |
| Arena backward compat (no regression) | ✅ 521 tests pass |
| **Phase 4E-2: Match Integration & Permadeath** | |
| Hero loads into PlayerState at match join | ✅ Complete |
| Permadeath on hero death (is_alive=false) | ✅ Complete |
| Post-match persistence (loot, gold saved) | ✅ Complete |
| hero_select WS message in lobby | ✅ Complete |
| Arena backward compat (no hero required) | ✅ 556 tests pass |
| **Phase 4E-3: Town Hub Client UI** | |
| Town Hub screen with tab navigation | ✅ Complete |
| Hiring Hall component (hero cards, hire button) | ✅ Complete |
| Hero Roster component (owned heroes, select for dungeon) | ✅ Complete |
| GameState profile/hero/gold reducers | ✅ Complete |
| Screen flow: Lobby → Town → Dungeon | ✅ Complete |
| Post-match summary screen | ✅ Complete |
| Permadeath notification UI | ✅ Complete |
| Arena mode completely unaffected | ✅ 556 tests pass |
| **Phase 5 Feature 6: Merchant System** | |
| Merchant config (stock, buy prices, sell multiplier) | ✅ Complete |
| REST endpoints (stock, buy, sell) | ✅ Complete |
| Merchant.jsx component (buy/sell panels, hero selector) | ✅ Complete |
| Town Hub merchant tab enabled | ✅ Complete |
| GameState MERCHANT_BUY/SELL reducers | ✅ Complete |
| Confirmation modal + transaction feedback | ✅ Complete |
| Grimdark CSS theme | ✅ Complete |
| Full backward compat | ✅ 594 tests pass |
| **Phase 5 Feature 7: Town Gear Management** | |
| REST endpoints (equip, unequip, transfer) | ✅ Complete |
| Hydrate/serialize helpers for Equipment/Inventory | ✅ Complete |
| HeroDetailPanel.jsx (stats, equipment, bag, transfer) | ✅ Complete |
| HeroRoster click-to-manage integration | ✅ Complete |
| GameState HERO_EQUIP/UNEQUIP/TRANSFER reducers | ✅ Complete |
| Equipment swap logic (occupied slot → bag) | ✅ Complete |
| Transfer modal with hero picker | ✅ Complete |
| Item tooltip + action feedback UI | ✅ Complete |
| Grimdark CSS theme (overlay, panel, slots, buttons) | ✅ Complete |
| Full backward compat | ✅ 627 tests pass |
| **Phase 6A: Skills Config & Server Models** | |
| Skills config (5 skills, class mapping) | ✅ Complete |
| SKILL ActionType + skill_id on PlayerAction | ✅ Complete |
| ActionResult skill fields (skill_id, buff_applied, heal_amount) | ✅ Complete |
| TurnResult buff_changes field | ✅ Complete |
| PlayerState active_buffs field | ✅ Complete |
| Skills loader module (skills.py) | ✅ Complete |
| WS whitelist updated for skill actions | ✅ Complete |
| Full backward compat | ✅ 752 tests pass |
| **Phase 6B: Turn Resolver Skill Phase & Combat Logic** | |
| Skill resolution phase (1.9) in turn resolver | ✅ Complete |
| Buff tick phase (0.75) — decrement + expire | ✅ Complete |
| Heal effect handler (self/ally, cap at max_hp) | ✅ Complete |
| Double Strike effect handler (multi-hit, armor per-hit) | ✅ Complete |
| Power Shot effect handler (1.8x ranged, LOS, own cooldown) | ✅ Complete |
| War Cry effect handler (self-buff, 2x melee) | ✅ Complete |
| Shadow Step effect handler (teleport, range/LOS/obstacle/occupied) | ✅ Complete |
| Buff effects in combat.py (melee/ranged multipliers) | ✅ Complete |
| Skill kills register in deaths + loot pipeline | ✅ Complete |
| Full backward compat | ✅ 827 tests pass |
| **Phase 6C: WebSocket Protocol & Client State** | |
| WS skill_id validation (reject missing/invalid) | ✅ Complete |
| match_start payload includes class_skills | ✅ Complete |
| turn_result includes active_buffs per player | ✅ Complete |
| skill_id in all queue serialization points | ✅ Complete |
| Client classSkills + allClassSkills state | ✅ Complete |
| Client TURN_RESULT reducer: skill log entries + floaters | ✅ Complete |
| ActionBar queue display for skill actions | ✅ Complete |
| Arena queue visualization for skill targets | ✅ Complete |
| Full backward compat | ✅ 858 tests pass |
| **Phase 6D: SkillBar UI & Canvas Targeting** | |
| SkillBar component (class-appropriate buttons) | ✅ Complete |
| Skill targeting mode + canvas highlights (purple) | ✅ Complete |
| Skill click handler (validates + queues action) | ✅ Complete |
| Cooldown overlay (grayed + turns remaining) | ✅ Complete |
| Active buff indicators on HUD | ✅ Complete |
| Self-targeting skills auto-queue on click | ✅ Complete |
| Party control support (ally class skills) | ✅ Complete |
| Skill targeting hints + tooltips | ✅ Complete |
| Full backward compat | ✅ 830 tests pass |
| **Phase 6E: Dungeon GUI Reorganization** | |
| 6E-1: CSS Grid layout foundation | ✅ Complete |
| 6E-2: HeaderBar component (turn/timer/HP/buffs) | ✅ Complete |
| 6E-3: Right panel cleanup (no redundancy, capped CombatLog) | ✅ Complete |
| 6E-4: BottomBar component (merge ActionBar + SkillBar) | ✅ Complete |
| 6E-5: Inventory overlay | ✅ Complete |
| 6E-6: Final polish & viewport verification | ✅ Complete |
| Pure client-side — 0 server files modified | ✅ 858 tests pass |
| **Phase 7A-1: Server Cooperative Movement Resolution** | |
| Batch movement resolver (`resolve_movement_batch`) | ✅ Complete |
| Swap detection (two units exchange positions) | ✅ Complete |
| Chain moves (A→B→C→empty all succeed) | ✅ Complete |
| Cycle/rotation detection (3+ units rotating) | ✅ Complete |
| Same-target conflict resolution (human > AI, then ID) | ✅ Complete |
| Stationary-blocker detection (non-movers still block) | ✅ Complete |
| Turn resolver integration (replaces sequential loop) | ✅ Complete |
| Full backward compat | ✅ 908 tests pass |
| **Phase 7A-2: Client-Side Ally-Aware Pathfinding** | |
| `generateSmartActions` accepts `friendlyUnitKeys` param | ✅ Complete |
| Friendly units excluded from A* occupied set | ✅ Complete |
| Move highlights allow stepping through allies | ✅ Complete |
| Arena.jsx computes & passes friendly unit keys | ✅ Complete |
| Pure client-side — 0 server files modified | ✅ 908 tests pass |
| **Phase 7A-3: Movement Prediction for Queued Paths** | |
| `_build_occupied_set()` helper with pending_moves prediction | ✅ Complete |
| `decide_ai_action()` accepts `pending_moves` parameter | ✅ Complete |
| All AI behavior functions (aggressive/ranged/boss) use predicted occupied set | ✅ Complete |
| Helper functions (patrol/reinforce/pursue) use predicted occupied set | ✅ Complete |
| `run_ai_decisions()` tracks pending MOVE intents across sequential AI calls | ✅ Complete |
| Client `generateSmartActions()` accepts `pendingMoves` parameter | ✅ Complete |
| Client `generateGroupPaths()` for multi-unit sequential path computation | ✅ Complete |
| Full backward compat (pending_moves=None is default) | ✅ 926 tests pass |
| **Phase 7B-1: Server-Side Multi-Control** | |
| `set_party_control()` additive — no release-previous | ✅ Complete |
| `select_all_party()` selects all alive hero allies | ✅ Complete |
| `release_all_party()` releases all controlled units | ✅ Complete |
| `queue_group_action()` same action for multiple units | ✅ Complete |
| `queue_group_batch_actions()` per-unit batch paths | ✅ Complete |
| WS messages: `select_all_party`, `release_all_party`, `group_action`, `group_batch_actions` | ✅ Complete |
| `get_controlled_unit_ids()` works with multiple units | ✅ Complete |
| Full backward compat | ✅ 963 tests pass |
| **Phase 7B-2: Client-Side Multi-Selection UI** | |
| `selectedUnitIds` array added to GameStateContext | ✅ Complete |
| `TOGGLE_UNIT_SELECTION` reducer for shift-click toggle | ✅ Complete |
| `SELECT_ALL_PARTY` reducer selects all alive party + self | ✅ Complete |
| `DESELECT_ALL_UNITS` reducer clears selection | ✅ Complete |
| Arena.jsx shift-click on ally toggles multi-select | ✅ Complete |
| Arena.jsx click empty space deselects all | ✅ Complete |
| Arena.jsx Ctrl+A keyboard shortcut for Select All | ✅ Complete |
| PartyPanel shift-click toggle + primary/secondary display | ✅ Complete |
| PartyPanel "Select All" / "Deselect All" group buttons | ✅ Complete |
| ArenaRenderer multi-select rings (cyan primary, gold secondary) | ✅ Complete |
| BottomBar multi-select badge indicator | ✅ Complete |
| CSS styles for primary, secondary, group buttons, badges | ✅ Complete |
| Pure client-side — 0 server files modified | ✅ 963 tests pass |
| **Phase 7B-3: Group Right-Click Movement** | |
| `spreadDestinations()` BFS for group destination assignment | ✅ Complete |
| `computeGroupRightClick()` leader selection + follower spreading | ✅ Complete |
| Arena.jsx group right-click handler (multi-unit → `group_batch_actions`) | ✅ Complete |
| `group_batch_queued` WS response handler in App.jsx | ✅ Complete |
| `GROUP_BATCH_QUEUED` reducer updates partyQueues for all batch units | ✅ Complete |
| PartyPanel group movement indicator (⇶ icon when group-queued) | ✅ Complete |
| Hallway-aware destination spreading (BFS naturally lines up in corridors) | ✅ Complete |
| Full backward compat — single-unit right-click unchanged | ✅ 953 tests pass |
| **Phase 7C-1: Stance Model & Server Logic** | |
| `ai_stance` field on PlayerState (`follow` default) | ✅ Complete |
| `VALID_STANCES` constant (`follow`, `aggressive`, `defensive`, `hold`) | ✅ Complete |
| Follow stance: path toward owner, regroup >4 tiles, fight nearby | ✅ Complete |
| Aggressive stance: pursue enemies freely, return to owner >5 tiles | ✅ Complete |
| Defensive stance: stay within 2 tiles of owner, attack nearby only | ✅ Complete |
| Hold Position stance: never move, attack enemies in range only | ✅ Complete |
| `_find_owner()` helper (controlled_by → same-team human fallback) | ✅ Complete |
| `decide_ai_action()` dispatches hero allies to stance behavior | ✅ Complete |
| Enemy AI ignores stances (backward compat) | ✅ Complete |
| `set_unit_stance()` in match_manager (per-unit stance setting) | ✅ Complete |
| `set_all_stances()` in match_manager (bulk stance setting) | ✅ Complete |
| `set_stance` / `set_all_stances` WS message handlers | ✅ Complete |
| `ai_stance` in party snapshot, players snapshot, match_start payload | ✅ Complete |
| Full backward compat | ✅ 1003 tests pass |
| **Phase 7C-2: Stance WS Protocol & State** | |
| Client `stance_updated` / `all_stances_updated` WS handlers (App.jsx) | ✅ Complete |
| `STANCE_UPDATED` / `ALL_STANCES_UPDATED` reducers (GameStateContext) | ✅ Complete |
| WebSocket protocol doc updated (set_stance, set_all_stances, responses) | ✅ Complete |
| 7 new WS protocol tests (match_start payload, snapshot reflection, persistence) | ✅ Complete |
| Full backward compat | ✅ 1009 tests pass |
| **Phase 7D-1: Multi-Layer Pathfinding (Path Through Closed Doors)** | |
| Server `a_star()` / `get_next_step_toward()` accept `door_tiles` param | ✅ Complete |
| Door tiles removed from blocked set, +3 weighted cost applied | ✅ Complete |
| `_maybe_interact_door()` helper — AI INTERACT when adjacent to closed door | ✅ Complete |
| `decide_ai_action()` passes `door_tiles` to hero ally stances only | ✅ Complete |
| Follow / Aggressive / Defensive stances: all MOVE paths wrapped with door check | ✅ Complete |
| Enemy AI excluded — never receives `door_tiles`, cannot open doors | ✅ Complete |
| `match_tick()` builds `door_tiles` set from `door_states`, passes to `run_ai_decisions()` | ✅ Complete |
| Client `aStar()` accepts `doorTiles` param, weighted cost (+3) | ✅ Complete |
| `_buildActionsWithDoorInteractions()` — inserts INTERACT before MOVE onto doors | ✅ Complete |
| `generateSmartActions()` all 5 intents pass `doorSet` to A* + door post-processing | ✅ Complete |
| `generateGroupPaths()` / `spreadDestinations()` / `computeGroupRightClick()` pass `doorSet` | ✅ Complete |
| Arena.jsx `doorSet` useMemo + passed to all right-click paths | ✅ Complete |
| `obstacleSet` still includes closed doors (for highlights); `doorSet` separate layer for A* | ✅ Complete |
| Full backward compat | ✅ 1064 tests pass |
| **Phase 7D-2: Diagonal Door Interaction** | |
| `_is_chebyshev_adjacent()` function — 8-directional adjacency check | ✅ Complete |
| Door INTERACT uses Chebyshev adjacency (all 8 tiles) | ✅ Complete |
| Chest LOOT unchanged — still cardinal-only (`_is_cardinal_adjacent`) | ✅ Complete |
| Existing `test_dungeon_doors.py` diagonal test updated (now asserts success) | ✅ Complete |
| Full backward compat | ✅ 1091 tests pass |
| **Phase 7D-3: AI Door Opening (For Follow Stance)** | |
| `_maybe_interact_door()` stateless helper — AI INTERACT when adjacent to closed door | ✅ Complete |
| Follow / Aggressive / Defensive stances: all MOVE paths wrapped with door check | ✅ Complete |
| Defensive stance bug fix: enemy-approach now uses door-aware A* | ✅ Complete |
| Hold stance: never opens doors (never moves) — verified | ✅ Complete |
| Enemy AI exclusion — never receives `door_tiles`, cannot open doors | ✅ Complete |
| `decide_ai_action()` dispatches `door_tiles` to hero ally stances only | ✅ Complete |
| Turn resolver integration: AI INTERACT opens door, ally moves through next tick | ✅ Complete |
| Full backward compat | ✅ 1090 tests pass |
| **Phase 7E-1: Pathfinding Preview Improvements** | |
| Hover path preview for ALL selected units (different colors per unit) | ✅ Complete |
| Door interaction point overlays (🚪 icon at door crossings) | ✅ Complete |
| Formation ghost preview at destination (ghost circles per unit) | ✅ Complete |
| Real-time path recalculation on cursor move (tile-boundary optimized) | ✅ Complete |
| `computeHoverPreview()` in pathfinding.js (single + group preview) | ✅ Complete |
| `drawHoverPathPreviews()` in ArenaRenderer.js (5-color palette rendering) | ✅ Complete |
| Arena.jsx `hoverPreviews` useMemo + optimized `handleCanvasMouseMove` | ✅ Complete |
| Disabled during actionMode (attack/ranged/skill/interact highlights take precedence) | ✅ Complete |
| Pure client-side — 0 server files modified | ✅ 1118 tests pass |
| **Phase 8A-1: AI Potion Usage — `_should_use_potion()` Helper** | |
| `_should_use_potion()` helper function (scan inventory, prefer highest magnitude) | ✅ Complete |
| Per-stance HP threshold constants (follow=40%, aggressive=25%, defensive=50%, hold=40%) | ✅ Complete |
| Integration into `_decide_stance_action()` as highest-priority check | ✅ Complete |
| Greater health potion preferred over regular (magnitude-sorted) | ✅ Complete |
| Non-heal consumables ignored (portal scrolls, equipment) | ✅ Complete |
| Enemy AI exclusion — enemies never route through `_decide_stance_action` | ✅ Complete |
| Full backward compat | ✅ 1146 tests pass |
| **Phase 8E-1: Ranged DPS AI — `_ranged_dps_skill_logic()` (Ranger Power Shot)** | |
| `_ranged_dps_skill_logic()` — Power Shot decision (range + LOS + cooldown) | ✅ Complete |
| Weighted target selection via `_pick_best_target()` (low-HP priority) | ✅ Complete |
| Secondary target fallback when best target out of range/LOS | ✅ Complete |
| Class `ranged_range` used for Power Shot range (Ranger=6, Inquisitor=5) | ✅ Complete |
| `_try_skill()` validation (class restriction + cooldown check) | ✅ Complete |
| Integration via `_decide_skill_usage()` dispatch (ranged_dps role) | ✅ Complete |
| Enemy AI exclusion — enemies never route through skill logic | ✅ Complete |
| Guard tests (wrong class, no class, enemy AI) | ✅ Complete |
| Full backward compat | ✅ 1233 tests pass |
| **Phase 8K-1: AI Retreat Helpers & Constants** | |
| `_RETREAT_THRESHOLDS` per-role HP retreat constants (tank=15%, support=35%, ranged=25%, hybrid=20%, scout=25%) | ✅ Complete |
| `_has_heal_potions()` helper — lightweight inventory scan for heal consumables | ✅ Complete |
| `_should_retreat()` decision helper — HP threshold + no potions + in danger + not hold stance | ✅ Complete |
| `_find_retreat_destination()` — smart retreat toward support ally / owner / generic flee | ✅ Complete |
| Door-aware retreat pathing (`_maybe_interact_door` integration) | ✅ Complete |
| Full backward compat | ✅ 1343 tests pass |
| **Phase 8K-2: Retreat Integration into Stance Dispatch** | |
| Retreat priority layer in `_decide_stance_action()` (between potion and skill checks) | ✅ Complete |
| `occupied` set pre-computation in `_decide_stance_action()` (passed to stance handlers) | ✅ Complete |
| Stance handlers accept `precomputed_occupied` parameter (follow/aggressive/defensive/hold) | ✅ Complete |
| Retreat fallthrough to skill/combat when cornered | ✅ Complete |
| Full backward compat | ✅ 1343 tests pass |
| **Phase 8K-3: Ranged Kiting (Ranger & Inquisitor)** | |
| Ranged role kiting in `_decide_follow_action()` — step back when dist ≤ 2 to enemy | ✅ Complete |
| Ranged role kiting in `_decide_aggressive_stance_action()` — same kiting logic | ✅ Complete |
| Melee rush gate — ranged roles excluded from `dist_to_target <= 3` rush branch | ✅ Complete |
| Cornerered fallback — melee attack when no retreat tile available | ✅ Complete |
| Defensive/hold stances excluded from kiting (by design) | ✅ Complete |
| Non-ranged classes (Crusader, Hexblade, Confessor) unaffected | ✅ Complete |
| Full backward compat | ✅ 1363 tests pass |
| **Phase 8K-4: AI Retreat & Kiting Tests** | |
| `_has_heal_potions()` tests (5 tests: potion, empty, equipment, non-heal, mixed) | ✅ Complete |
| `_should_retreat()` tests (8 tests: low HP, potions, threshold, danger zone, hold, per-role, null class) | ✅ Complete |
| `_find_retreat_destination()` tests (7 tests: toward confessor, toward owner, flee, door-aware, cornered, priority, too-far) | ✅ Complete |
| Priority chain integration tests (8 tests: potion over retreat, retreat over skill, fallthrough, all stances) | ✅ Complete |
| Guard / regression tests (4 tests: enemy AI, full HP, null class, enemy kiting) | ✅ Complete |
| Full backward compat | ✅ 1395 tests pass |
| **Wave Arena — AI Testing Map** | |
| Wave Arena map (20×20, open layout, 4 pillars) | ✅ Complete |
| Wave spawner system (8 waves, progressive difficulty) | ✅ Complete |
| Wave state management (init, clear check, advance) | ✅ Complete |
| Victory suppression until final wave cleared | ✅ Complete |
| `wave_started` WS broadcast + client combat log entry | ✅ Complete |
| Map loader `get_wave_spawner_config()` helper | ✅ Complete |
| Lobby map dropdown (WaitingRoom + Lobby) | ✅ Complete |
| Free-roaming wave enemies (no room leashing) | ✅ Complete |
| Full backward compat | ✅ 1428 tests pass |
| **Phase 9: Particle Effects Lab** | |
| Particle effects system (damage, heal, buff, teleport, death) | ✅ Complete |
| Particle lab tool (standalone testing environment) | ✅ Complete |
| Client particle renderer integration | ✅ Complete |
| **Phase 10: Auto-Target Pursuit (10A–10F)** | |
| 10A: Server model — `auto_target_id` on PlayerState | ✅ Complete |
| 10B: Server — `generate_auto_target_action()` (A* chase + melee) | ✅ Complete |
| 10C: WebSocket protocol — `set_auto_target` / `auto_target_set` / `auto_target_cleared` | ✅ Complete |
| 10D: Client state — `autoTargetId` + right-click pursuit | ✅ Complete |
| 10E: Visual feedback — pulsing reticle + HUD target frame + combat log | ✅ Complete |
| 10F: Edge cases — death cleanup, queue override, unreachable, party members | ✅ Complete |
| **Phase 10G: Skill & Ability Auto-Target Pursuit (10G-1 through 10G-8)** | |
| 10G-1: Server model — `auto_skill_id` field + `set_auto_target()` skill validation | ✅ Complete |
| 10G-2: Server — skill-aware `generate_auto_target_action()` (range/LOS/cooldown) | ✅ Complete |
| 10G-3: WebSocket protocol — `skill_id` in auto-target messages + turn_result sync | ✅ Complete |
| 10G-4: Client state — `selectedTargetId` + `autoSkillId` + reducers | ✅ Complete |
| 10G-5: Client — left-click target selection + gold/green selection ring | ✅ Complete |
| 10G-6: Client — target-first skill casting (BottomBar + `isInSkillRange`) | ✅ Complete |
| 10G-7: Visual feedback — skill-aware HUD, colored reticles, selected target pane, CSS | ✅ Complete |
| 10G-8: Edge cases & tests — 11 new edge case tests + 22 core tests (66 total auto-target tests pass) | ✅ Complete |
| **Phase 12: The Dungeon Run** | |
| **12A: Complete Crusader & Ranger Skill Kits** | ✅ Complete |
| **12B: Crowd Control / Status Effects (Stun, Slow, Taunt, Evasion)** | ✅ Complete |
| **12C: Portal Scroll — Extraction Mechanic** | ✅ Complete |
| 3-turn channeled cast (scroll consumed, caster locked in place) | ✅ Complete |
| Portal entity spawns on caster's tile (20-turn duration, turn counter) | ✅ Complete |
| Per-hero extraction via INTERACT `enter_portal` (E-key) | ✅ Complete |
| Channeling/extracted guards on all turn resolver phases | ✅ Complete |
| Dungeon victory conditions (`dungeon_extract` / `party_wipe`) | ✅ Complete |
| Portal rendering (animated purple glow, concentric rings, turn counter) | ✅ Complete |
| Channeling bar above caster during cast | ✅ Complete |
| Portal HUD prompt ("↯ Enter Portal — Press E to escape") | ✅ Complete |
| Extracted heroes hidden from canvas (vanish on extraction) | ✅ Complete |
| Auto-release control when active unit extracts (switch to next hero) | ✅ Complete |
| AI portal retreat (hero allies pathfind to portal and auto-extract) | ✅ Complete |
| Portal combat log color (purple `#cc66ff`) | ✅ Complete |
| Portal particle presets (5 presets: ring, glow, sparks, swirl, flash) | ✅ Complete |
| Particle Lab compound mode (multi-layer preview for portal effects) | ✅ Complete |
| 20 portal scroll tests passing | ✅ Complete |
| **12D: Multi-Floor Dungeon Progression** | 🔲 Planned |
| **12E: Procedural Dungeon Integration** | 🔲 Planned |
| **12F: Rare Item Tier & Loot Expansion** | 🔲 Planned |
| **12G: Mini-Map & Explored Tile Memory** | 🔲 Planned |
| **12H: Sound & Audio Foundation** | 🔲 Planned |

| **Phase 13: Path Forward** | |
| **13-1A: Dead File Purge** | ✅ Complete |
| **13-1B: Remove Unused Dependency (socket.io-client)** | ✅ Complete |
| **13-1C: Deduplicate Shared Functions** | ✅ Complete |
| **13-1D: Extract PostMatchScreen** | ✅ Complete |
| **13-1E: Stale Config Cleanup** | ✅ Complete |

| **Phase 14: Visual Feedback & Combat Clarity** | |
| **14A: New Particle Presets (9 unmapped skills)** | ✅ Complete |
| **14B: Wire All Skills in Effect Mapping** | ✅ Complete |
| **14C: DoT/HoT Tick Floaters** | ✅ Complete |
| **14D: Miss / Dodge / Blocked Floaters** | ✅ Complete |
| **14E: Stun & Slow Visual Overlays** | ✅ Complete |
| **14F: Critical / Overkill Hit Emphasis** | 🟨 Not started |
| **14G: Ranged Projectile Travel System** | 🔲 Planned |
| **14H: Persistent Status Effect Overlays** | 🔲 Planned |
| **14I: AoE Ground Indicators** | 🔲 Planned |

### Test Suite

- **2178+ tests passing** (0 failures, 1 pre-existing flaky test in test_turn_resolver)
- Coverage: match lifecycle, combat, turn resolution, action queue, WebSocket protocol, team management, lobby chat, in-lobby config, AI-in-lobby, config lock fix, smart spawn system, dungeon map loading, room/door/chest parsing, dungeon match creation, arena regression, door interaction, FOV with doors, movement + doors, ranged through doors, phase timing, enemy config loading, dungeon enemy spawning, AI behavior dispatch, room leashing, retreat logic, server payloads, item models, loot generation, loot table validation, equipment bonuses in combat, loot drops on death, chest interaction, ground item pickup, inventory cap, equip/unequip, health potion use, portal scroll rejection, phase ordering, hero models, hero stats variation, hero generation, name generation, JSON persistence, tavern generation, hiring flow, town REST endpoints, hero-match integration, permadeath, post-match persistence, merchant stock, merchant buy, merchant sell, merchant flow, town gear equip, town gear unequip, town gear transfer, gear swap logic, hydrate/serialize roundtrip, skill config loading, skill lookups, skill validation, skill model fields, class-skill mapping, skill effect handlers (heal, multi-hit, ranged, buff, teleport), buff tick system, skill-combat integration, skill phase ordering, WS skill action validation, match_start class_skills, players snapshot active_buffs, queue skill_id serialization, skill definition cross-reference, cooperative movement batch resolver, swap detection, chain moves, cycle rotation, contested tile resolution, movement prediction (build_occupied_set, pending moves, hallway chain prediction, backward compat), multi-select (additive control, select_all_party, release_all_party, group_action, group_batch_actions, controlled unit IDs, validation, regression), group movement (batch paths, destination spreading, hallway formation, mixed actions, validation, single-unit regression), AI stances (follow/aggressive/defensive/hold behavior, stance dispatch, owner lookup, stance management, snapshot inclusion, backward compat), door-aware A* pathfinding (weighted door cost, door-in-obstacles priority, multi-door paths, _maybe_interact_door helper, AI hero ally door opening, enemy AI exclusion, edge cases), diagonal door interaction (Chebyshev adjacency, 8-directional door INTERACT, cardinal-only chest LOOT preserved), AI door opening (multi-tick resume, multi-door crossing, all stances verified, enemy AI regression, turn resolver integration, defensive bug fix), AI potion usage (_should_use_potion helper, stance threshold integration, magnitude-sorted potion preference, heal-only filtering, enemy AI exclusion, edge cases), AI ranged DPS skills (Power Shot decision, range + LOS validation, weighted target selection + fallback, dispatch integration, enemy AI exclusion, class guard), AI retreat behavior (retreat thresholds, _has_heal_potions, _should_retreat, _find_retreat_destination, retreat priority integration, occupied pre-computation), AI ranged kiting (Ranger/Inquisitor kiting in follow + aggressive stances, melee rush gate, cornered fallback, stance exclusions, class guards), AI retreat tests (_has_heal_potions inventory scanning, _should_retreat decision logic per-role thresholds, _find_retreat_destination smart targeting, priority chain integration, guard/regression), wave spawner system (map loader, wave state init, wave clear detection, wave advancement, enemy count per wave, victory suppression, wave state cleanup, edge cases)
- Client builds cleanly (0 errors)
- Phase 4A: Backward compat verified — class_id=null uses default stats
- Phase 4B-1: Full backward compat — all arena maps and existing tests unaffected
- Phase 4B-2: Full backward compat — all arena and 4B-1 tests unaffected; 40 new door mechanic tests
- Phase 4C: Full backward compat — all arena AI unaffected; 43 new enemy type tests
- Phase 4D-1: Full backward compat — all existing tests unaffected; 87 new item/loot tests
- Phase 4D-2: Full backward compat — all existing tests unaffected; 48 new equipment/loot/combat tests
- Phase 4D-3: Pure client-side — 0 server files modified; 0 test regressions
- Phase 4E-1: Full backward compat — all existing tests unaffected; 75 new hero/persistence/town tests
- Phase 4E-2: Full backward compat — all existing tests unaffected; 35 new hero-match/permadeath tests
- Phase 4E-3: Pure client-side — 0 server files modified; 0 test regressions; client builds cleanly
- Phase 5 F6: Full backward compat — all existing 564 tests unaffected; 30 new merchant tests; client builds cleanly
- Phase 5 F7: Full backward compat — all existing 594 tests unaffected; 33 new gear management tests; client builds cleanly
- Phase 6A: Full backward compat — all existing 691 tests unaffected; 61 new skill config/model/validation tests
- Phase 6B: Full backward compat — all existing 752 tests unaffected; 75 new skill combat/integration tests
- Phase 6C: Full backward compat — all existing 827 tests unaffected; 31 new WS skill protocol tests; client builds cleanly
- Phase 6D: Pure client-side — 0 server files modified; 0 test regressions; client builds cleanly
- Phase 6E (1-3): Pure client-side — 0 server files modified; 0 test regressions; client builds cleanly
- Phase 6E-4: Pure client-side — 0 server files modified; 0 test regressions; client builds cleanly
- Phase 6E-5: Pure client-side — 0 server files modified; 0 test regressions; client builds cleanly
- Phase 6E-6: Pure client-side — 0 server files modified; 0 test regressions; client builds cleanly; dead code removed (ActionBar, SkillBar deleted)
- Phase 7A-1: Full backward compat — all existing 858 tests unaffected; 33 new cooperative movement tests (batch resolver, swap, chain, cycle, contested tile, regression)
- Phase 7A-2: Pure client-side — 0 server files modified; 0 test regressions; client builds cleanly
- Phase 7A-3: Full backward compat — all existing 908 tests unaffected; 18 new movement prediction tests (build_occupied_set, pending_moves, hallway chain, decide_ai_action, run_ai_decisions tracking); client builds cleanly
- Phase 7B-1: Full backward compat — all existing 926 tests unaffected; 37 new multi-select tests (additive select, select_all, release_all, group_action, group_batch, controlled IDs, validation, regression)
- Phase 7B-2: Pure client-side — 0 server files modified; 0 test regressions; client builds cleanly
- Phase 7B-3: Full backward compat — all existing 935 tests unaffected; 18 new group movement tests (batch paths, validation, hallway scenarios, mixed actions, regression); client builds cleanly
- Phase 7C-1: Full backward compat — all existing 953 tests unaffected; 50 new stance tests (model, helpers, follow/aggressive/defensive/hold behavior, dispatch, persistence, match_manager management, snapshot inclusion, backward compat)
- Phase 7C-2: Full backward compat — all existing 1003 tests unaffected; 6 new WS protocol tests (match_start payload includes stance, stance changes reflected in party/players snapshots, set_all_stances reflected, multiple changes persist); client builds cleanly
- Phase 7D-1: Full backward compat — all existing 1037 tests unaffected; 27 new door pathfinding tests (weighted A* door cost, open route preference, multi-door paths, door-in-obstacles priority, _maybe_interact_door helper, follow/aggressive/defensive stance door opening, enemy AI exclusion, edge cases); client builds cleanly
- Phase 7D-2: Full backward compat — all existing 1064 tests unaffected; 27 new diagonal door interaction tests (Chebyshev adjacency helper, 8-directional door INTERACT, cardinal-only chest LOOT regression guard, distance validation)
- Phase 7D-3: Full backward compat — all existing 1063 tests unaffected; 27 new AI door opening tests (multi-tick resume for follow/aggressive/defensive, multi-door crossing, hold stance exclusion, enemy AI regression guard, defensive bug fix, turn resolver integration, edge cases); 1 bug fix (defensive enemy-approach missing door_tiles)
- Phase 7E-1: Pure client-side — 0 server files modified; 0 test regressions; client builds cleanly; hover path preview with multi-unit colors, door icons, formation ghosts
- Phase 8A-1: Full backward compat — all existing 1118 tests unaffected; 28 new AI potion usage tests (_should_use_potion helper, stance threshold constants, potion preference by magnitude, non-heal exclusion, enemy AI exclusion guard, integration with _decide_stance_action)
- Phase 8E-1: Full backward compat — all existing 1216 tests unaffected; 17 new ranged DPS AI tests (_ranged_dps_skill_logic Power Shot decision, range + LOS validation, target selection + fallback, dispatch integration, enemy AI exclusion guard, wrong class guard, null class guard)
- Phase 8K-1/8K-2: Full backward compat — all existing 1233 tests unaffected; 110 new AI retreat tests (_RETREAT_THRESHOLDS constants, _has_heal_potions helper, _should_retreat decision, _find_retreat_destination smart targeting, retreat integration in _decide_stance_action priority chain, occupied set pre-computation, retreat fallthrough when cornered)
- Phase 8K-3: Full backward compat — all existing 1343 tests unaffected; 20 new ranged kiting tests (Ranger/Inquisitor kiting in follow + aggressive stances, melee rush gate for ranged roles, cornered fallback, defensive/hold exclusion, non-ranged class guards, null class guard, enemy AI regression)
- Phase 8K-4: Full backward compat — all existing 1363 tests unaffected; 32 new retreat/kiting tests (_has_heal_potions inventory scanning, _should_retreat decision logic with per-role thresholds, _find_retreat_destination smart targeting with door-awareness, priority chain integration via _decide_stance_action, guard/regression tests for enemy AI exclusion and null class safety)
- Wave Arena: Full backward compat — all existing 1395 tests unaffected; 33 new wave spawner tests (map loader, wave state init, first wave spawn, team assignment, free-roaming enemies, wave clear detection, wave advancement, enemy count per wave, victory suppression, wave state cleanup, spawn point cycling, wave ID prefixes, full 8-wave progression)
- Phase 10 (10A–10F): Full backward compat — persistent melee pursuit via auto_target_id; 33 new auto-target tests (set/clear, chase/attack generation, door interaction, queue override, party members, persistence, multi-attacker, death cleanup)
- Phase 10G (10G-1–10G-8): Full backward compat — skill auto-target pursuit via auto_skill_id; 22 core 10G tests + 11 dedicated 10G-8 edge case tests (skill switching, class restriction mid-pursuit, heal overheal, party member skill pursuit, multi-cycle persistence, team change defence); client builds cleanly; 66 total auto-target tests pass
- Combat Meter: Pure client-side — 0 server files modified; 0 test regressions; client builds cleanly; 5 stat views (damage done/taken, healing, kills, overview), Tab hotkey toggle, class-colored bars, per-turn rates
- Phase 16A: Full backward compat — all existing 1665 tests unaffected; 60 new stat expansion tests; 1725 total tests pass; 10 server files modified, 1 client file, 3 test files updated for tuple return compat; new damage pipeline (dodge→armor pen→flat armor→%DR→crit→life on hit→thorns); 16 new combat stats (crit, dodge, DR, armor pen, HP regen, life on hit, thorns, CDR, skill/heal/dot/holy damage %, move speed, gold/magic find); equipment aggregation with configurable caps
- Phase 16E: Full backward compat — all existing 1994 tests unaffected; 104 new set item tests; 2098 total tests pass; 5 sets (Crusader's Oath, Voidwalker's Regalia, Deadeye's Arsenal, Faith's Radiance, Seeker's Judgment), 15 set pieces, 2 bonus tiers per set (2/3 and 3/3), highest-tier-wins stat aggregation, skill modifiers (taunt duration, wither duration, CDR, thorns, ward reflect, range bonuses), special effects (ranged crit pierce), drop rules (0.3% base, elite/boss only, floor scaling, class affinity weighting, per-run dedup), equipment manager integration with automatic set bonus recalculation on equip/unequip; new files: sets_config.json, set_bonuses.py; modified: player.py, equipment_manager.py, item_generator.py, loot.py, skills.py, itemUtils.js, SetEditor.jsx
- Phase 18I: Enemy Identity Skills — 42 new tests (2416 total); 5 new skills: enrage (passive trigger at 30% HP, permanent +50% damage buff for Demon), bone_shield (self-cast 25-damage absorb barrier for Skeleton, damage_absorb effect type), frenzy_aura (tag-filtered passive +3 attack_damage aura for Imp packs), dark_pact (ally +25% melee damage buff for Dark Priest, replacing shield_of_faith), profane_ward (ally 30% damage reduction buff for Acolyte, replacing shield_of_faith); new effect types: passive_enrage, damage_absorb, passive_aura_ally_buff with tag filter; updated class_skills for demon_enrage, skeleton, imp_frenzy, dark_priest, acolyte; AI integration: bone_shield cast on visible enemy, dark_pact targets highest-damage ally; modified: skills_config.json (5 skills + 5 class_skills entries), enemies_config.json (class_id updates), turn_resolver.py, combat.py, skills.py, ai_skills.py; new test file: test_enemy_skills.py
- Phase 18H: Enemy Forge Tool — standalone dev tool (tools/enemy-forge/); Vite + React + Express; 8 tabs: Enemy Browser with search/filter, Enemy Editor with stat sliders/role/AI/tags/canvas preview, Affix Editor with compatibility rules, Champion Type Editor, Floor Roster Viewer, TTK Simulator with party config + N-encounter simulation, Spawn Preview with distribution charts, Super Unique Editor with retinue/loot/flavor text; Export Panel with diff preview + auto-backup; server.js reads/writes enemies_config.json, monster_rarity_config.json, super_uniques_config.json; launch via start-enemy-forge.bat; documented in docs/Tools/enemy-forge.md and docs/Systems/enemy-forge.md
- Phase 18G: Super Uniques — 63 new tests (2344 total); 4 hand-crafted bosses: Malgris the Defiler (demon, extra_strong + fire_enchanted, imp+acolyte retinue), Serelith Bonequeen (necromancer, regenerating + might_aura + cold_enchanted, skeleton+undead_caster retinue), Gorvek Ironhide (construct, stone_skin + thorns + shielded, construct retinue), The Hollow King (undead_knight, extra_strong + cursed + stone_skin + conviction_aura, demon_knight+dark_priest retinue); super_uniques_config.json with fixed stats/affixes/retinues/loot tables; 25% per-floor spawn chance on eligible floors; max 1 per run; unique loot tables with guaranteed rare+ and unique item chance; config loader with caching + validation in monster_rarity.py; map_exporter.py boss replacement logic; modified: monster_rarity.py, map_exporter.py, loot.py; new: super_uniques_config.json, test_super_uniques.py
- Phase 18D: Combat Integration — 33 new tests (2305 total); _resolve_auras() for Might Aura (+25% damage) and Conviction Aura (-3 armor) as refreshing 1-turn buffs/debuffs; on-hit effect hooks in combat.py (Cursed: +1 cooldown, Cold Enchanted: 30% slow, Mana Burn: +2 highest cooldown, Spectral Hit: 20% life steal); on-death explosions in _resolve_deaths() (Fire Enchanted: 20 dmg/2 tiles, Possessed champion: 15 dmg/1 tile); Ghostly phase-through in ai_pathfinding.py (_build_occupied_set returns empty set for ghostly champions); Teleporter auto-cast Shadow Step in ai_behavior.py (3-turn cooldown, triggers at 4+ tile distance); hp_regen verified in existing _resolve_cooldowns_and_buffs; Shielded affix Ward verified in _apply_affix_effect; minion unlinking on rare leader death in _resolve_deaths(); new: test_monster_rarity_combat.py
- Phase 18C: Spawn Integration — 28 new tests (2272 total); rarity rolling wired into map_exporter.py export_to_game_map() for dungeon enemy spawns; match_manager.py _spawn_dungeon_enemies() applies rarity via apply_rarity_to_player() + spawns rare minions; wave_spawner.py rarity support with wave-as-floor scaling; champion pack spawning (2-3 same-type champions on adjacent BFS tiles); rare minion placement via BFS open tile search; monster_rarity/champion_type/affixes/display_name added to WebSocket broadcast in get_players_snapshot() and advance_floor(); new: test_monster_rarity_spawn.py
- Phase 18B: Affix engine implementation — 71 new tests (150 total monster rarity tests); added roll_monster_rarity() with floor scaling & min floor requirements, roll_champion_type(), roll_affixes() with full compatibility rules (max aura, max on-death, forbidden combos, excluded_affixes, ranged_only, excludes_class_skills), generate_rare_name() D2-style naming, apply_rarity_to_player() with 4-step stat application (tier multipliers -> champion type -> affix effects -> HP recalc), create_minions() for rare leader packs; all functions tested in isolation + end-to-end flows; 2249+ total tests pass; zero behavior changes to existing systems
- Phase 18A: Full backward compat — all existing 2098+ tests unaffected; 79 new monster rarity data model tests; 2178+ total tests pass; zero behavior changes; new files: monster_rarity_config.json (rarity tiers, 5 champion types, 15 affixes, affix rules, spawn chances), monster_rarity.py (config loader, validation, accessors); modified: player.py (6 new PlayerState fields, 2 new EnemyDefinition fields), enemies_config.json (allow_rarity_upgrade + excluded_affixes for bosses, training dummy, constructs, shadow-step enemies)
