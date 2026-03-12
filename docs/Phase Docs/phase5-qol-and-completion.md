# Phase 5: Quality of Life & Core Loop Completion — Design Document

## Overview

**Goal:** Polish the dungeon crawler experience with essential QoL improvements and complete the core gameplay loop.

**Timeline:** 3-4 weeks  
**Status:** In Progress  
**Prerequisites:** Phase 4 (4A-4E-3) complete

---

## Phase 4 Status

**Completed (Core Features):**
- ✅ 5 playable classes (Crusader, Confessor, Inquisitor, Ranger, Hexblade)
- ✅ Hero hiring and permadeath system
- ✅ Handcrafted dungeons with rooms, corridors, doors
- ✅ 3 enemy types with AI behaviors
- ✅ Full loot and inventory system (Common/Uncommon gear)
- ✅ Equipment system with stat bonuses
- ✅ Town hub with hiring hall and hero roster
- ✅ Post-match death summaries and hero persistence

**Deferred from Phase 4:**
- Portal scroll escape mechanic (4F)
- ~~Merchant buy/sell system (4F)~~ → ✅ Completed in Phase 5 Feature 6
- AI enemy parties with group tactics (4G)
- Final balance pass (4G)

**Current State:** Game is playable but needs QoL polish and loop completion.

---

## Phase 5 Scope

### Focus Areas



**2. Core Loop Completion**
- Portal scroll escape mechanic
- Merchant system (buy scrolls, sell loot)
- AI enemy parties
- Balance pass

**Not Included:**
- New classes (Phase 6+)
- Procedural dungeon generation (Phase 6+)
- Rare/Unique loot tiers (Phase 6+)
- Additional enemy types (Phase 6+)
- Multiple dungeon floors (Phase 6+)


## Feature 4: Starting Gold Adjustment

**Problem:** Starting gold may be too low for testing and balance.

**Solution:** Increase starting gold from current value to 1000g.

### Changes

**Server:**
- Update default starting gold in profile creation
- Existing profiles unaffected (or migrate if needed)

**Impact:**
- Players can hire 2-3 heroes initially (at 200-400g each)
- Enough buffer to buy portal scrolls and basic gear
- Reduces early-game frustration

**Testing:**
- Verify new profiles start with 1000g
- Test economy balance (is 1000g too much or too little?)

---

## Feature 5: Portal Scroll Escape Mechanic - ** DEFER TIL AFTER FEATURE 6 MERCHANT IS COMPLETE SEE FEATUER 6 BELOW **

**Problem:** No way to exit dungeon mid-run. Players must clear entire dungeon or die.

**Solution:** Portal scroll consumable item allows party-wide escape to town.

### Behavior

**Portal Scroll Item:**
- Consumable item (appears in inventory)
- Can be used at any time during dungeon run
- **Party-wide effect:** One scroll extracts entire party

**Using Portal Scroll:**
1. Player uses portal scroll from inventory
2. All living party members extracted immediately
3. Match ends for all players
4. All players return to town hub
5. Loot in hero inventories is saved
6. Dead heroes remain dead (permadeath already applied)
7. Gold earned from run is saved

**Acquisition:**
- Purchase from town merchant (50-100g each)
- Occasionally drops from enemies or chests (rare)
- Players typically bring 1-2 scrolls per dungeon run

**Strategic Decision:**
- Escape now with current loot (safe)
- OR continue deeper for more loot (risky)

### Requirements

**Server:**
- Portal scroll item definition
- USE_ITEM action for portal scroll
- Match end logic triggered by portal use
- Loot persistence on escape (already exists from permadeath system)

**Client:**
- Portal scroll usage from inventory
- Confirmation prompt: "Use portal scroll? All party members will be extracted."
- Visual effect (portal animation or flash)
- Return to town hub after use

---

## Feature 6: Merchant System ✅ COMPLETE

**Problem:** No way to buy portal scrolls or sell loot for gold.

**Solution:** Town merchant NPC for buying and selling items.

**Status:** ✅ Implemented — 30 tests passing, client builds cleanly, 594 total tests

### Functionality

**Merchant Stock (Buy):**
- Portal scrolls (75g each)
- Greater Health Potions (55g)
- Basic starter gear (Common quality)
  - Weapons: Rusty Sword +5 atk (50g), Shortbow +8 rng (50g), Iron Mace +8 atk (55g)
  - Armor: Chainmail +3 arm (40g), Leather +4 arm (45g), Plate +6 arm (60g)
  - Accessories: Iron Ring +20 HP (30g), Bone Amulet +30 HP (45g)
- Health potions (25g each)

**Sell to Merchant:**
- Uses each item's `sell_value` from items_config.json
- Common gear: 10-18g
- Uncommon gear: 35-60g
- Vendor buys any item from hero inventory
- Configurable sell_multiplier (default 1.0)

**Merchant UI:**
- Tab in Town Hub (next to Hiring Hall, Hero Roster) — enabled and functional
- Left panel: Merchant stock (buy) — categorized by type
- Right panel: Selected hero's inventory (sell)
- Hero selector tabs for choosing which hero to buy for / sell from
- Click item → confirmation modal with price
- Gold balance always visible
- Rarity color coding (common=gray, uncommon=green)
- Stat previews on all items
- Transaction success/error feedback messages

### Implementation

**Server:**
- `merchant_config.json` — Merchant stock with buy prices and categories
- REST endpoints:
  - `GET /api/town/merchant/stock` — Returns buyable items with full definitions and buy prices
  - `POST /api/town/merchant/buy` — Purchase item, deduct gold, add to hero inventory
  - `POST /api/town/merchant/sell` — Sell item by index, credit gold, remove from hero inventory
- Gold transaction validation (insufficient gold, inventory full, dead hero, invalid item)
- Items persist via existing hero profile system (JSON file persistence)

**Client:**
- `Merchant.jsx` component in TownHub folder
- `MERCHANT_BUY` / `MERCHANT_SELL` reducer actions in GameStateContext
- Two-column buy/sell layout with hero selector
- Confirmation modal for all transactions
- Full CSS with grimdark theme consistency

**Tests (30 new):**
- Stock endpoint: returns items, required fields, consumables, equipment, prices
- Buy: success, gold deduction, inventory add, multiple buys, insufficient gold, full inventory, dead hero, invalid item, invalid hero, missing username, equipment items, portal scroll
- Sell: success, gold credit, inventory removal, uncommon items, consumables, invalid indices, dead hero, empty inventory, missing username
- Flow: buy→sell round-trip, buy multiple sell some, gold economy consistency

---

## Feature 7: AI Enemy Parties

**Problem:** Dungeons only have individual AI enemies. No simulation of player vs player encounters.

**Solution:** Spawn AI-controlled enemy parties (3-4 units using player classes) in dungeons.

### Behavior

**Enemy Party Composition:**
- 3-4 units using player classes
- Example: 1 Crusader, 1 Confessor, 2 Rangers
- Equipped with gear (Common/Uncommon)

**Spawning:**
- 1-2 enemy parties per dungeon run
- Spawn in specific rooms or patrol corridors
- Do not respawn on death

**Group AI Behavior:**
- Move as coordinated group (stay in formation)
- Tank in front, healer/ranged in back
- Focus-fire on weakest player target (lowest HP)
- Use abilities/attacks based on class role
- Retreat if heavily outnumbered (optional behavior)

**Loot Rewards:**
- Defeat enemy party → loot all equipped gear (100% drop rate)
- High-risk, high-reward encounter
- Significantly better loot than regular enemies

### Requirements

**Server:**
- Enemy party spawn definitions in dungeon config
- Group AI behavior logic
  - Formation movement (maintain relative positions)
  - Role-based positioning (tank forward, support back)
  - Target prioritization (lowest HP player)
- Loot drop on party defeat (drop all equipped gear)

**Client:**
- Visual differentiation for enemy parties (group indicator, different colors)
- Combat log messages for enemy party actions

### Notes

**Group AI Complexity:**
- Start simple: individual AI units that stay near each other
- Upgrade to coordinated tactics if time allows
- Formation movement can use "follow leader" pattern

**Balance:**
- Enemy party should be challenging but not impossible
- Test with 2-player party vs 3-unit enemy party
- Adjust stats/gear if too hard or too easy

---

## Feature 8: Balance Pass

**Problem:** Game systems exist but may not be balanced. Gold economy, enemy difficulty, loot rates need tuning.

**Solution:** Playtesting and iterative balance adjustments.

### Areas to Balance

**Gold Economy:**
- Starting gold: 1000g (locked in)
- Hiring costs: 200-400g (locked in)
- Portal scroll cost: 50-100g (tune based on testing)
- Loot sell values: Common 10-25g, Uncommon 25-75g (tune based on testing)
- **Goal:** Player should afford new hero after 2-3 successful dungeon runs

**Enemy Difficulty:**
- Enemy HP, damage, armor values
- Enemy density (how many per room)
- Boss difficulty
- AI party strength
- **Goal:** Challenging but not punishing. Deaths should feel fair, not cheap.

**Loot Drop Rates:**
- Chest spawn frequency
- Enemy loot drop chance
- Common vs Uncommon ratio
- Portal scroll drop rate (rare but possible)
- **Goal:** Players find upgrades regularly but not every run

**Class Balance:**
- Class base stats (HP, damage, armor, vision)
- Are all classes viable?
- Is any class overpowered or underpowered?
- **Goal:** All 5 classes feel useful and distinct

### Process

**Playtesting:**
1. Run 10+ dungeon runs with different party compositions
2. Track: deaths, gold earned, loot found, time per run
3. Identify pain points and imbalances

**Tuning:**
1. Adjust values in config files (not code)
2. Re-test
3. Iterate until balance feels good

**No specific targets here - this is trial and error based on feel.**

---

## Development Timeline

### Week 1: QoL Improvements

**Focus:** Movement and attack quality of life.

**Deliverables:**
- Click-to-destination movement with path preview
- Auto-attack system (click enemy, auto-path + attack)
- Starting gold updated to 1000g

**Testing:**
- Movement feels smooth and intuitive
- Auto-attack handles edge cases (enemy moves, path blocked)
- Path previews are clear and accurate

---

### Week 2: UI Redesign

**Focus:** In-game and town interface overhaul.

**Deliverables:**
- Redesigned action bar, HUD, combat log, inventory screen
- Redesigned town hub (hiring hall, hero roster, merchant placeholder)
- Grimdark theme consistency
- Improved readability and usability

**Testing:**
- UI is visually appealing and thematic
- All screens are easy to navigate
- No usability regressions

---

### Week 3: Core Loop Completion

**Focus:** Portal scrolls and merchant system.

**Deliverables:**
- Portal scroll escape mechanic
- Merchant buy/sell system
- Full loop: hire → dungeon → loot → escape → sell → repeat

**Testing:**
- Portal scroll extracts entire party
- Merchant transactions work correctly
- Gold economy feels balanced
- Full loop is playable end-to-end

---

### Week 4: AI Parties & Balance

**Focus:** Enemy parties and final polish.

**Deliverables:**
- AI enemy parties with group behavior
- 100% loot drop on enemy party defeat
- Balance pass (gold economy, enemy difficulty, loot rates, class stats)
- Bug fixes and polish

**Testing:**
- AI parties provide challenging encounters
- Loot rewards feel worth the risk
- Economy is balanced (can sustain multiple runs)
- No critical bugs in core loop

---

## Success Criteria

**Phase 5 is complete when:**

- ✅ Click-to-destination movement works smoothly
- ✅ Auto-attack system handles common cases (melee, ranged, pathing)
- ✅ UI redesign is complete and visually polished
- ✅ Starting gold is 1000g
- ✅ Portal scroll escape mechanic functional
- ✅ Merchant buy/sell system working
- ✅ AI enemy parties spawn and behave as groups
- ✅ Balance feels good (economy, difficulty, loot rates)
- ✅ Full gameplay loop playable: hire → dungeon → loot → escape → sell → repeat
- ✅ 0 critical bugs blocking core loop
- ✅ Existing arena mode still functional

---

## Known Issues & Tech Debt

**To Address in Phase 5:**
- Movement tedium (Feature 1 fixes this)
- Attack workflow clunkiness (Feature 2 fixes this)
- UI needs polish (Feature 3 fixes this)
- No escape mechanic (Feature 5 fixes this)
- No merchant (Feature 6 fixes this)
- No PvP simulation (Feature 7 fixes this)

**Deferred to Phase 6+:**
- Procedural dungeon generation
- Additional classes (Dark Knight, Plague Doctor, etc.)
- Rare/Unique loot with affixes
- Multiple dungeon floors
- Class abilities/skills beyond basic attacks
- Real player vs player parties

---

**Document Version:** 1.1  
**Created:** February 13, 2026  
**Updated:** February 13, 2026 — Feature 6 (Merchant System) implemented  
**Status:** In Progress  
**Prerequisites:** Phase 4 (4A-4E-3) Complete
