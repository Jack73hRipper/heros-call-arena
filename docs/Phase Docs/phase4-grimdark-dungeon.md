# Phase 4: Grimdark Dungeon Crawler — Design Document

## Overview

**Goal:** Transform arena combat into a co-op dungeon crawler with permadeath, hero hiring, loot, and PvP encounters.

**Theme:** Grimdark fantasy (Dark Souls/Bloodborne aesthetic)

**Timeline:** 6-8 weeks  
**Status:** Planning Phase  
**Prerequisites:** Phase 3 complete

---

## Core Vision

**The Loop:**
1. **Town Hub:** Hire hero from tavern, equip gear, buy portal scrolls
2. **Form Party:** 2-5 players in lobby, select their hired heroes
3. **Enter Dungeon:** Explore handcrafted dungeon, fight AI enemies, find loot
4. **Choice:** Use portal scroll to escape with loot OR continue deeper (future: stairs down)
5. **Encounters:** Potentially face other parties (AI-controlled for Phase 4 testing)
6. **Escape or Die:** Return to town to sell/trade loot, or lose everything on death

**Stakes:** Heroes permadeath. Death = lose hero and all equipped gear forever. Must re-hire.

**Progression:** No leveling. Progression through better equipment only.

---

## Phase 4 Scope

### What's Included

**Class System:**
- 5 playable classes with distinct roles
- Each class has unique base stats (HP, damage, armor, vision range)
- Unique visual sprites (grimdark aesthetic)
- Different playstyles (tank, healer, scout, ranged DPS, hybrid DPS)

**Hero Hiring System:**
- Tavern/hiring hall in town hub
- Random pool of available heroes (multiple of same class with stat variations)
- View hero card: name, class, base stats, equipped gear
- Hiring costs gold
- Permadeath: dead hero = lost forever

**Dungeon:**
- Handcrafted test dungeon (1 floor for Phase 4)
- Multiple rooms connected by corridors
- 20x20 or 25x25 map size
- AI enemies placed throughout
- Loot chests and enemy drops

**AI Enemies:**
- 3 enemy types (melee, ranged, mini-boss)
- Use existing AI pathfinding and combat systems
- Different stats and behaviors per type

**Loot System (Simple):**
- Common (white) gear: basic stats (+5 damage, +10 HP)
- Uncommon (blue) gear: slightly better stats
- Health potions (consumable, restore HP)
- Portal scrolls (consumable, party-wide escape)
- Gear equips to hero slots: weapon, armor, accessory

**PvP Encounters (AI Parties):**
- AI-controlled enemy parties in dungeon (simulates player parties)
- Enemy party composition: 3-4 units using player classes
- Behaves like player party (group movement, tactics, use abilities)
- Defeating enemy party = loot their equipped gear (100% drop rate)

**Town Hub (Minimal):**
- Hiring hall (hire heroes)
- Merchant (sell loot for gold, buy portal scrolls)
- Basic UI for managing inventory

### What's Not Included (Future Phases)

- Procedural dungeon generation (Phase 5+)
- Player trading / global chat (Phase 5+)
- Multiple dungeon floors / stairs down (Phase 5+)
- Diablo 2-style rare/unique/set items (Phase 5+)
- Real player vs player parties (Phase 5+)
- Open instance matchmaking (Phase 5+)
- Hero resurrection mechanics (deferred - needs more design)
- Advanced skills/abilities per class (Phase 5+ - start with basic attacks)

---

## Class Roster (Full Vision)

### Starting 5 Classes (Phase 4)

**1. Crusader (Tank)**
- Role: Front-line protector, high HP and armor, anti-undead
- Playstyle: Absorb damage, protect allies, punish enemies
- Base Stats: High HP, moderate damage, high armor, short vision

**2. Confessor (Healer)**
- Role: Keep party alive, remove debuffs, support
- Playstyle: Heal allies, cleanse status effects, utility
- Base Stats: Moderate HP, low damage, low armor, moderate vision

**3. Inquisitor (Scout)**
- Role: Information gathering, reveal enemies, detect dangers
- Playstyle: Extended vision, mark enemies, early warning
- Base Stats: Low HP, low damage, moderate armor, extended vision

**4. Ranger (Ranged DPS)**
- Role: High damage from distance, kiting, precision
- Playstyle: Stay at range, maximize damage, avoid melee
- Base Stats: Low HP, high ranged damage, low armor, moderate vision

**5. Hexblade (Hybrid DPS)**
- Role: Versatile fighter, magic and melee, adaptable
- Playstyle: Cast spells at range, engage in melee when needed
- Base Stats: Moderate HP, moderate damage (both types), moderate armor, moderate vision

### Future Classes (Phase 5+)

**Tanks:**
- **Dark Knight** - Corrupted warrior, lifesteal, self-sustaining

**Healers:**
- **Plague Doctor** - Hex healing, disease manipulation

**Scouts:**
- **Tracker** - Ranged scout, survival expert, mark targets

**Support:**
- **Thaumaturge** - Arcane manipulation, buffs/debuffs, utility
- **Troubadour** - Inspiration, morale, party-wide buffs
- **Blightbringer** - Disease/poison, summon and control rats

**Ranged DPS:**
- **Alchemist** - Potion thrower, explosive flasks, area denial

**Melee DPS:**
- **Shadowblade** - Quick strikes, backstab, critical hits
- **Berserker** - Rage, high damage, reckless aggression

**Summoner:**
- **Bone Collector** - Raise dead, necromancy, corpse magic

---

## Hero Hiring System

### Tavern/Hiring Hall

**Concept:** Players don't create custom characters. They hire pre-generated heroes with random stat variations.

**Hiring Flow:**
1. Visit tavern in town hub
2. View available heroes (random pool, refreshes periodically?)
3. Each hero shows:
   - Generated name (e.g., "Gareth the Crusader", "Elara the Ranger")
   - Class
   - Base stats (HP, damage, armor, vision)
   - Currently equipped gear (starts with basic equipment)
   - Hiring cost (gold)
4. Select hero and pay gold to hire
5. Hero joins your roster
6. Bring hired hero into dungeon runs

**Stat Variations:**

Same class, different heroes have slightly different stats.

Example:
- **Crusader A:** 150 HP, 20 melee damage, 8 armor, 6 vision
- **Crusader B:** 140 HP, 22 melee damage, 7 armor, 6 vision

Creates variety and choice. Do you want the tankier or more aggressive Crusader?

**Hiring Cost:**
- Better base stats = higher hiring cost
- Incentivizes risk/reward (expensive hero = more to lose on death)

### Permadeath

**When hero dies in dungeon:**
- Hero is lost forever
- All equipped gear on hero is lost
- Must hire new hero to continue playing

**No resurrection in Phase 4.** (Deferred for future design - may add expensive town resurrection or in-dungeon revival in Phase 5+)

---

## Dungeon Structure

### Phase 4 Dungeon

**Layout:**
- Handcrafted test dungeon (not procedural)
- 1 floor
- 20x20 or 25x25 map size
- 5-8 rooms connected by corridors
- Starting room (safe spawn point)
- Loot rooms (contain chests)
- Enemy rooms (AI spawns)
- Boss room (mini-boss encounter)

**Design Goals:**
- Test class synergy (tank protects healer, scout reveals ahead)
- Test loot acquisition
- Test party vs AI party encounters
- Controlled environment for balance testing

**Future (Phase 5+):**
- Procedural generation
- Multiple floors with stairs down
- Increasing difficulty per floor

---

## AI Enemies

### Enemy Types (Phase 4)

**1. Melee Demon**
- Behavior: Aggressive, chase nearest player, melee attack
- Stats: Moderate HP, moderate damage, low armor
- Threat: Front-line danger, blocks corridors

**2. Ranged Skeleton**
- Behavior: Maintain distance, ranged attack, retreat if approached
- Stats: Low HP, moderate ranged damage, low armor
- Threat: Harass from afar, forces positioning decisions

**3. Mini-Boss (Undead Knight)**
- Behavior: Aggressive, high HP, strong attacks, slower movement
- Stats: High HP, high damage, high armor
- Threat: Room guardian, requires team focus to defeat
- Loot: Always drops uncommon (blue) gear

**AI Behavior:**
- Reuse existing AI pathfinding and scouting systems from Phase 2-3
- Enemies patrol rooms, engage on sight (FOV-based)
- No special abilities in Phase 4 (just move + attack)

---

## Loot System

### Phase 4 (Simple System)

**Rarity Tiers:**
- **Common (White):** Basic gear, low stat bonuses
- **Uncommon (Blue):** Better stats, more valuable

**Item Types:**
- **Weapons:** Increase damage (+5 to +15)
- **Armor:** Increase armor (+3 to +10)
- **Accessories:** Increase HP (+20 to +50)
- **Health Potions:** Consumable, restore 30-50 HP
- **Portal Scrolls:** Consumable, party-wide escape from dungeon

**Drop Sources:**
- Loot chests in rooms
- Enemy deaths (chance-based)
- Mini-boss guaranteed uncommon drop
- Enemy party defeats (100% equipped gear drop)

**Equip Slots (Per Hero):**
- Weapon
- Armor
- Accessory

**Inventory Management:**
- Hero carries limited items (10 slots?)
- Party shares inventory or individual inventories? (Design decision needed)

### Future (Phase 5+)

**Diablo 2-Style Loot:**
- **Common (White):** Plain items, no affixes
- **Magic (Blue):** 1-2 random affixes
- **Rare (Yellow):** 3-4 random affixes, powerful
- **Unique (Gold):** Named items, fixed special effects
- **Set Items (Green):** Collect multiple pieces for set bonuses

**Random Affixes:**
- +damage, +HP, +armor, lifesteal, fire damage, poison on hit, etc.

---

## PvP Encounters

### Phase 4: AI-Controlled Enemy Parties

**Concept:** Simulate player vs player by spawning AI-controlled parties in dungeon.

**Enemy Party Composition:**
- 3-4 units using player classes (e.g., 1 Crusader, 1 Confessor, 2 Rangers)
- Acts as coordinated group (not individual AI units)
- Uses player class stats and equipment

**Behavior:**
- Patrols dungeon as a group
- Engages player party on sight (FOV-based detection)
- Uses tactics: tank in front, healer in back, ranged at distance
- Attempts to focus fire on weakest player target

**Loot Rewards:**
- Defeating enemy party = loot all equipped gear (100% drop rate)
- High-risk, high-reward encounter
- Encourages players to engage or strategically avoid

**Spawn:**
- 1-2 enemy parties per dungeon run
- Spawns in specific rooms or patrols corridors

### Future (Phase 5+)

**Real Player vs Player:**
- Multiple human parties in same dungeon instance
- Proximity-based encounters
- Last party standing escapes with all loot
- Open instance matchmaking (any number of parties can join)

---

## Dungeon Escape Mechanic

### Portal Scrolls

**Functionality:**
- Consumable item
- **Party-wide effect:** One scroll escapes entire party (all members don't need their own)
- Can be used at any time in dungeon
- Returns party to town hub with all collected loot

**Acquisition:**
- Purchase from town merchant (affordable, ~50-100 gold each)
- Occasionally drops from enemies or chests

**Strategy:**
- Players bring 1-2 portal scrolls per run
- Decision: escape now with current loot OR push deeper and risk death
- If all scrolls used and party dies = lose everything

**Future (Phase 5+):**
- Stairs down at end of each floor
- Choice: use portal to escape OR take stairs to next (harder) floor

---

## Town Hub

### Phase 4 Town Features

**Hiring Hall:**
- View available heroes for hire
- Hire heroes with gold
- See hero stats and equipment before hiring

**Merchant:**
- Sell loot for gold
- Buy portal scrolls (affordable)
- Buy basic gear (common quality, starter equipment)

**Inventory Management:**
- View heroes in roster
- Equip gear on heroes
- Store items in bank? (Design decision needed)

### Future (Phase 5+)

**Player Trading:**
- Global chat
- Trade items/gold with other players

**Advanced Merchants:**
- Specialty vendors (enchanter, blacksmith, alchemist)
- Rare item vendors (expensive uniques)

**Guild Hall / Social Hub:**
- Form persistent parties
- Shared storage

---

## Development Timeline

### Week 1-2: Class System Foundation

**Deliverables:**
- 5 class definitions (stats, visuals)
- Class selection in lobby (replace generic units)
- Unique sprites for each class (grimdark aesthetic)
- Class-specific base stats implemented (HP, damage, armor, vision)

**Testing:**
- Each class feels distinct
- Visual differentiation clear
- Stats balanced for roles

---

### Week 3-4: Hero Hiring & Permadeath

**Deliverables:**
- Hiring hall UI (town hub)
- Hero generation system (random names, stat variations)
- Hero card display (stats, gear, cost)
- Hiring with gold cost
- Permadeath on hero death

**Testing:**
- Can hire heroes successfully
- Stat variations create meaningful choices
- Permadeath triggers correctly

---

### Week 5-6: Dungeon & Loot

**Deliverables:**
- Handcrafted dungeon (1 floor, 5-8 rooms)
- 3 AI enemy types (melee, ranged, mini-boss)
- Loot drops (common/uncommon weapons, armor, accessories)
- Health potions and portal scrolls
- Chest spawns in rooms
- Item equip system

**Testing:**
- Dungeon layout supports exploration
- AI enemies provide challenge
- Loot feels rewarding

---

### Week 7-8: PvP Encounters & Polish

**Deliverables:**
- AI-controlled enemy parties (3-4 units)
- Enemy party behavior (group tactics)
- Loot enemy parties on defeat (100% drop)
- Portal scroll escape mechanic
- Town merchant (sell loot, buy scrolls)

**Testing:**
- Enemy parties feel like player opponents
- Portal escape works reliably
- Full loop functional: hire → dungeon → loot → escape → sell

---

## Success Metrics

### Core Gameplay Validation

**Class Diversity:**
- Each class feels necessary (tank, healer, scout, DPS roles matter)
- Party composition affects success rate

**Permadeath Stakes:**
- Players care about hero survival
- Death feels impactful (not trivial)
- Hiring new heroes is meaningful choice

**Loot Loop:**
- Finding loot is exciting
- Gear upgrades noticeably improve hero power
- Escape vs push-deeper decision creates tension

**PvP Encounters:**
- AI parties provide challenge
- Defeating enemy party feels rewarding
- Loot reward justifies risk

### Playtesting Goals

**Questions to Answer:**
- Are 5 classes enough variety, or need more immediately?
- Is permadeath too punishing or appropriately tense?
- Does handcrafted dungeon feel too repetitive after 5+ runs?
- Is loot drop rate satisfying (too rare, too common)?
- Do players bring portal scrolls or forget and die?
- Are AI enemy parties too easy, too hard, or balanced?

---

## Phase 4 → Phase 5 Transition

### After Phase 4 Completion, Evaluate:

**Green Light for Phase 5 if:**
- Class system works (roles matter, diversity is fun)
- Permadeath creates tension without frustration
- Loot loop is satisfying (want to keep running dungeons)
- AI parties simulate PvP well
- Players request more classes, more dungeons, more loot variety

**Phase 5 Scope (Conditional):**
- Add 5 more classes (Dark Knight, Plague Doctor, Tracker, Alchemist, Shadowblade)
- Procedural dungeon generation
- Multiple floors with stairs down
- Diablo 2-style loot (rare/unique/set items, random affixes)
- Player trading and global chat
- Real player vs player parties

**Yellow Light (Iterate Phase 4) if:**
- Classes feel too similar (need more differentiation)
- Permadeath too harsh (need resurrection mechanic)
- Loot system too simple (need rarity/affixes sooner)
- Handcrafted dungeon too repetitive (need procedural ASAP)

---

## Open Design Questions (To Resolve During Development)

1. **Inventory System:**
   - Shared party inventory or individual hero inventories?
   - How many item slots per hero?

2. **Gold Economy:**
   - Starting gold amount?
   - Hiring costs per class?
   - Loot sell values?
   - Portal scroll cost?

3. **Enemy Spawn Density:**
   - How many enemies per room?
   - Respawn on death or static spawns?

4. **Party Size:**
   - Lock at 4 players (balanced party) or allow 2-5 (flexible)?

5. **Loot Distribution:**
   - Free-for-all pickup (first to grab gets it)?
   - Round-robin auto-distribution?
   - Need-before-greed rolls?

6. **Hero Name Generation:**
   - Procedural names or curated list?
   - Class-specific name themes?

---

**Document Version:** 1.0  
**Created:** February 12, 2026  
**Status:** Planning Phase  
**Theme:** Grimdark Fantasy (Dark Souls/Bloodborne)
