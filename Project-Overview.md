```
    __  __                  _          ______      ____
   / / / /__  _________   ( )_____   / ____/___ _/ / /
  / /_/ / _ \/ ___/ __ \ /|// ___/  / /   / __ `/ / / 
 / __  /  __/ /  / /_/ /  (__  )  / /___/ /_/ / / /  
/_/ /_/\___/_/   \____/  /____/   \____/\__,_/_/_/   
                                                      
                    A  R  E  N  A
```

<p align="center">
  <em>A grimdark co-op dungeon crawler with permadeath, turn-based tactical combat, and a loot system worth dying for.</em>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/version-v0.1.8-blue" alt="Version" />
  <img src="https://img.shields.io/badge/tests-3987_passing-brightgreen" alt="Tests" />
  <img src="https://img.shields.io/badge/classes-11_playable-purple" alt="Classes" />
  <img src="https://img.shields.io/badge/platform-Windows_|_Desktop-lightgrey" alt="Platform" />
  <img src="https://img.shields.io/badge/status-Active_Development-orange" alt="Status" />
</p>

---

## The Arena

You don't get to be the chosen one. You get to hire some poor bastard from a tavern, strap a rusty sword to his back, and shove him into a dungeon full of things that want to eat him. If he makes it out alive, you keep the loot. If he doesn't — and he probably won't — you lose him and everything he was carrying. Permanently.

**Hero's Call Arena** is a turn-based co-op dungeon crawler where nothing is safe. Champion packs roam the halls with shared aura buffs. Rare elites roll random affixes that change how you have to fight them. Hand-crafted super unique bosses guard the deepest rooms with their own retinues and loot tables. Your party of five is all that stands between a fat haul of gear and a total wipe.

### Core Loop

```
  Town Hub  -->  Form Party  -->  Enter Dungeon  -->  Fight & Loot  -->  Escape or Perish
     |                                                                         |
     '---- Hire new heroes, buy gear, sell loot, stash valuables <-------------'
```

**Death is not a setback. It's a reset.** Hero dies, hero is gone. Gear on that hero — gone. Portal scrolls are your only lifeline. Use one to extract your party with their loot, or push deeper and risk everything.

---

## Features

### Tactical Combat
- **Turn-based action queue** — Queue up to 10 actions ahead and watch them execute in fast 1-second ticks
- **11 playable classes** — Tank, healer, scout, ranged DPS, hybrid DPS, caster, support, and more — each with unique skills, stats, and identity
- **Skill system** — 40+ skills across all classes including heals, buffs, AoE, DoTs, summons, auras, and crowd control
- **Combat meter** — Live damage/healing/kill tracking with per-skill breakdowns

### Dungeons
- **Wave Function Collapse generation** — Every dungeon layout is unique, assembled from modular tile pieces
- **8 dungeon themes** — Each biome has distinct wall textures, floor patterns, props, and ambient lighting
- **Room archetypes** — Grand Cathedrals, Ritual Chambers, Torture Chambers, Ossuaries, Fungal Grottos, and more
- **Dynamic lighting** — Torches, braziers, and ritual circles cast flickering multi-tile glow through ambient darkness
- **Door system** — Rooms separated by chokepoint doors that create tactical bottlenecks

### Monster Rarity System
- **Diablo II-inspired tiers** — Normal, Champion, Rare, and Super Unique monsters
- **15 affixes** — Enemies can roll modifiers like Teleporter, Ghostly, Vampiric, Molten Death, and more
- **Champion packs** — Elites spawn with minion escorts and shared aura buffs
- **4 hand-crafted super uniques** — Malgris the Defiler, Serelith Bonequeen, Gorvek Ironhide, The Hollow King — each with fixed affixes, retinues, and unique loot tables

### Loot & Equipment
- **Procedural item generation** — Weapons, armor, and accessories with random affixes and stat rolls
- **Rarity tiers** — Common through Unique, plus 5 equipment sets with tiered set bonuses
- **Town economy** — Merchant for buying/selling, bank for shared stash, hiring hall for recruiting heroes
- **Permadeath stakes** — Die in the dungeon and everything your hero was carrying is lost forever

### AI & Party System
- **Party of up to 5** — Control a full party with stance-based AI (Follow, Aggressive, Defensive, Hold)
- **Smart AI companions** — Allies use skills, drink potions, retreat when low, seek treasure chests, and pathfind through doors
- **PvP, PvE, and PvPvE** — Fight other players, dungeon monsters, or both at once
- **Wave Arena mode** — 8 escalating waves for testing builds and strategies

### Visual & Audio
- **Grimdark aesthetic** — Dark fantasy theme with procedural tile rendering, particle effects, and ambient atmosphere
- **50+ particle effects** — Combat hits, skill casts, buff auras, projectile trails, death explosions, and ambient dungeon effects
- **Full audio system** — Categorized SFX for combat, skills, UI, movement, and ambient music
- **Fog of war** — Server-side recursive shadowcasting with shared team vision

---

## The Classes

| Class | Role | Identity |
|-------|------|----------|
| **Crusader** | Tank | Heavy-armored frontline. Highest HP and armor in the game. |
| **Confessor** | Support | Primary healer with protective buffs and party sustain. |
| **Inquisitor** | Scout | Long-range vision, ranged damage, and battlefield awareness. |
| **Ranger** | Ranged DPS | Highest ranged damage dealer. Glass cannon with long range. |
| **Hexblade** | Hybrid DPS | Melee/ranged hybrid with cursed blade magic. |
| **Mage** | Caster DPS | Arcane artillery. Magic bypasses 50% of armor. |
| **Bard** | Offensive Support | Buffs allies while dealing respectable damage. |
| **Blood Knight** | Sustain Melee | Life-stealing melee fighter who heals through violence. |
| **Plague Doctor** | Controller | DoTs, debuffs, and area denial through poison and plague. |
| **Revenant** | Retaliation Tank | Punishes attackers with thorns and retaliatory damage. |
| **Shaman** | Totemic Healer | Deploys totems for healing, buffs, and area control. |

---

## Quick Start

### Prerequisites
- **Python 3.11+** and **Node.js 18+**

### One-Click Launch
```bash
start-game.bat          # Starts backend + frontend together
```
The game opens at `http://localhost:5173`. That's it.

### Manual Setup
```bash
# Backend
cd server
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000

# Frontend (separate terminal)
cd client
npm install
npm run dev
```

### Desktop App
```bash
start-electron.bat      # Launches the Electron desktop client
```

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| **Frontend** | React 18 · Vite · Canvas API · Custom particle engine |
| **Backend** | Python · FastAPI · WebSockets · Uvicorn |
| **Desktop** | Electron · electron-builder · PyInstaller |
| **Launcher** | Electron · Auto-updater · GitHub Releases |
| **Data** | JSON file persistence · Redis (optional) |
| **Testing** | pytest · 3,987 tests across 88 files · 0 failures |

---

## Dev Tools

The project includes **10 standalone development tools**, each launchable with a single batch file:

| Tool | Launch | Purpose |
|------|--------|---------|
| **WFC Dungeon Lab** | `start-dungeon-wfc.bat` | Design and test procedural dungeon layouts |
| **Cave Automata** | `start-cave-automata.bat` | Generate organic cave systems via cellular automata |
| **Particle Lab** | `start-particle-lab.bat` | Create and preview particle effects in real time |
| **Theme Designer** | `start-theme-designer.bat` | Preview procedural grimdark tile themes (8 biomes) |
| **Sprite Cataloger** | `start-sprite-cataloger.bat` | Browse and inspect sprite sheet assets |
| **Module Decorator** | `start-module-decorator.bat` | Paint visual tiles onto WFC dungeon modules |
| **Audio Workbench** | `start-audio-workbench.bat` | Preview sounds, A/B compare, edit audio configs |
| **Item Forge** | `start-item-forge.bat` | Create items, tune affixes, simulate drop rates |
| **Enemy Forge** | `start-enemy-forge.bat` | Edit monster rarity, affixes, TTK simulation |
| **Arena Analyst** | `start-arena-analyst.bat` | Match history, class balance analysis, trend charts |

---

## Project Architecture

```
Arena/
├── client/             # React frontend — UI, canvas renderer, particle engine, audio
├── server/             # Python backend — game logic, AI, combat, WebSocket server
│   ├── app/core/       #   Pure game logic (combat, AI, loot, WFC dungeons, skills)
│   ├── app/services/   #   Infrastructure (WebSocket, tick loop, persistence)
│   ├── app/routes/     #   REST + WS endpoints
│   ├── configs/        #   Game data (classes, enemies, items, maps, themes)
│   └── tests/          #   88 test files, 3,987 tests
├── tools/              # 10 standalone dev tools (React + Express)
├── launcher/           # Electron game launcher with auto-update
├── docs/               # 80+ design docs, system specs, and tool guides
└── build/              # Build artifacts, packaging configs, patch notes
```

> **Full documentation:** [docs/DOCS-ARCHITECTURE.md](docs/DOCS-ARCHITECTURE.md) — Master index of all 80+ project documents.

---

## Documentation Highlights

| Document | Description |
|----------|-------------|
| [Current Phase](docs/Current%20Phase.md) | Full milestone tracker — every feature and its status |
| [Class Overview](docs/class-overview.md) | Source of truth for all 11 classes, stats, and skills |
| [Combat System](docs/Systems/combat-system-overview.md) | Damage formulas, turn resolution, and combat mechanics |
| [WebSocket Protocol](docs/websocket-protocol.md) | All real-time message types and data shapes |
| [Project Audit](docs/project-audit-march-2026.md) | Architecture health assessment (8/10) |
| [Changelog](docs/changelog.md) | Full versioned history of every change |

---

## Latest Release — v0.1.8

*Dungeon Lighting, Door System, HUD Overhaul & AI Upgrades*

- **Prop lighting system** — Torches, braziers, and candelabras cast flickering multi-tile glow through ambient darkness
- **Room door system** — Wall separators with chokepoint doors at room boundaries
- **7 new room archetypes** — Grand Cathedral, Ritual Chamber, Torture Chamber, Burial Ground, Armory, Ossuary, Fungal Grotto
- **HUD overhaul** — Player/party HP bars, minimap relocation, 4-row grid layout
- **7 new skill particles** — Seal of Judgment, Blink, Bone Shield, Dark Pact, and more
- **AI upgrades** — Door-aware pathfinding, chest seeking, unique class compositions
- **Loot rebalance** — Location-based chest tiers, rarity curve adjustments

**3,987 tests passing.**

---

## Roadmap

The project has completed **27 major development phases** with active work continuing. Key areas of focus:

- **Online multiplayer** — Server hosting and matchmaking for real player-vs-player dungeon encounters
- **Combat meter expansion** — Per-skill breakdowns, team grouping, buff uptime tracking
- **Additional dungeon content** — New themes, room types, and boss encounters
- **Performance monitoring** — Client FPS overlay, server tick timing

---

<p align="center">
  <sub>Built with obsessive attention to grimdark detail · 80+ design docs · 3,987 tests · 0 failures</sub>
</p>
