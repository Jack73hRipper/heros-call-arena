# Buff Particle System Overhaul

**Status:** Tier 1 complete · Tier 2 complete · Tier 3 future  
**Phase:** Post-Phase 14 polish  
**Files touched:** `particle-presets.json`, `particle-effects.json`, `ParticleManager.js`, `Arena.jsx`

---

## Overview

The buff particle system was overhauled in three tiers to give buffs a strong visual identity. Players should always be able to *see* that a unit is buffed, what kind of buff it is, and roughly how strong it is — all from the particle effects alone.

---

## Tier 2: Persistent Buff Auras (COMPLETE)

### What was built

A new **persistent buff aura system** that mirrors the existing CC status particle system (`updateCCStatus`). While a unit has an active buff, a subtle looping particle aura plays continuously on that unit.

### Architecture

- **`buff_status` section** in `particle-effects.json` — maps buff types from `active_buffs[].type` to looping preset names
- **`buff_id_overrides`** — for the generic `buff` type, individual skills can specify different auras (e.g. War Cry gets orange embers, Shield of Faith gets golden stars)
- **`updateBuffStatus(players, visibleTiles)`** in `ParticleManager.js` — scans all players' `active_buffs` each tick, creates/destroys looping emitters
- **`_updateBuffEmitters()`** — repositions buff emitters to follow players each rAF frame
- **`_buffEmitters` Map** — tracks active buff emitters keyed by `${playerId}:${buffType}` or `${playerId}:buff:${buffId}`

### New Presets

| Preset Name | Buff Type | Visual Description |
|---|---|---|
| `buff-aura-war-cry` | `buff` (war_cry) | Slow-orbiting orange/red embers with trails, rising gently — aggressive warmth |
| `buff-aura-armor` | `buff` (shield_of_faith, default) | Faint golden star motes drifting upward — divine protection shimmer |
| `buff-aura-bulwark` | `buff` (bulwark) | Slow stone-colored square fragments with slight gravity — heavy, grounded |
| `buff-aura-ward` | `shield_charges` | Red orbiting motes with trails — reactive energy feel |
| `buff-aura-evasion` | `evasion` | Fast blue line streaks radiating outward — speed/agility wisps |
| `buff-aura-hot` | `hot` (prayer) | Gentle golden star sparkles rising softly — warm healing glow |
| `buff-aura-taunt` | `taunt` | Red/orange triangles with rotation — drawing aggro, threatening |

### Design Principles

- **Low particle count** (4–8 particles/sec) — auras are *ambient*, not distracting
- **Distinct shape per buff category**: circles for offensive, stars for holy/healing, squares for heavy armor, lines for agility, triangles for aggro
- **Distinct color per buff category**: orange/red for War Cry, gold for holy buffs, blue for evasion, red for ward, stone for bulwark
- **`maxParticles` capped at 25–45** — performance-safe even with 8+ buffed units on screen
- **yOffset support** — individual buff types can spawn above/below the unit center (e.g. HoT spawns slightly above)

### Wiring

- `Arena.jsx` calls `particleManager.updateBuffStatus(players, visibleTiles)` in the same `useEffect` that syncs player positions
- Boot diagnostic now cross-checks `buff_status` section against loaded presets

---

## Tier 1: Redesigned Buff Cast Animations (COMPLETE)

### What was built

Each buff skill's **activation effect** (the one-shot effect that plays when the skill is cast) was redesigned with a unique, impactful visual identity. Previously most buff casts looked like "gold dots going up" with minimal differentiation.

### Old → New Preset Mapping

| Skill | Old Preset | New Preset | Extras | Change Summary |
|---|---|---|---|---|
| War Cry | `buff-aura` | `war-cry-blast` | `war-cry-shockwave` | Gold dots → 40-particle flame burst (yellow→orange→red) + 30-particle expanding ground shockwave |
| Shield of Faith | `shield-of-faith-aura` | `faith-descend` | `faith-flash` | Rising stars → 30 golden star motes descending from above + 20-particle radial star flash |
| Bulwark | `bulwark-fortify` | `bulwark-slam` | `bulwark-dust` | Brief brown squares → 30 heavy stone fragments slamming down (gravity 140) + 22-particle dust cloud |
| Evasion | `evasion-blur` | `evasion-streak` | — | 10-particle blue dots → 28 fast line streaks with trails (white→blue), speed 130–220 |
| Prayer | `prayer-motes` | `prayer-blessing` | `prayer-ground-glow` | Basic rising stars → 22/sec growing stars (size 2→8) with long trails + 24-particle golden ground ring |

**Ward** (`ward-barrier`) was kept as-is — it was already the strongest of the original set.

### New Presets (9 total)

| Preset Name | Type | Particles | Duration | Shape | Colors | Key Feature |
|---|---|---|---|---|---|---|
| `war-cry-blast` | Main | 40 burst | 0.7s | Circle | #ffffcc → #ffcc00 → #ff6600 → #cc2200 | Aggressive upward flame burst |
| `war-cry-shockwave` | Extra | 30 burst | 0.6s | Circle | #ffee66 → #ff8800 → #cc3300 | 360° expanding ground ring |
| `faith-descend` | Main | 30 burst | 1.0s | Star | #ffffff → #ffeeaa → #ffcc44 → #ddaa22 | Motes descend from above, gravity 40 |
| `faith-flash` | Extra | 20 burst | 0.45s | Star | #ffffff → #fff5cc → #ffdd66 | Bright radial burst, size 6–11 |
| `bulwark-slam` | Main | 30 burst | 0.8s | Square | #ddddcc → #bbaa88 → #887766 → #443322 | Heavy slam, gravity 140, source-over blend |
| `bulwark-dust` | Extra | 22 burst | 0.7s | Circle | #ccbb99 → #998877 → #665544 | Dust cloud ring at ground level |
| `evasion-streak` | Main | 28 burst | 0.6s | Line | #ffffff → #aaddff → #66aaee → #3366aa | Speed 130–220, trail length 6 |
| `prayer-blessing` | Main | 22/sec | 1.5s | Star | #ffee44 → #ffffff → #ffffdd → #ffeeaa | Growing stars (2→8px), trail length 8 |
| `prayer-ground-glow` | Extra | 24 burst | 1.0s | Circle | #ffffdd → #ffee77 → #ddaa33 | Soft golden ring at feet |

### Design Principles

- **Every skill is visually distinct** — unique shape, color palette, and motion pattern
- **Shapes encode buff category**: circles for fire/offensive, stars for holy, squares for heavy armor, lines for agility
- **Colors encode buff identity**: red/orange/yellow for War Cry, white/gold for holy, grey/brown for armor, blue/white for evasion, warm gold for healing
- **Extras layer with main effects** via existing `extras` system — fire simultaneously at same position
- **High visibility** — burst counts 20–40, particle sizes 4–12px start, alpha starts at 0.8–1.0, ends at 0.1–0.2 (not zero)
- **No code changes** — entirely data-driven (preset JSON + mapping JSON)

### Skill Mapping Changes (`particle-effects.json`)

```json
"war_cry":        { "effect": "war-cry-blast",    "target": "caster", "extras": ["war-cry-shockwave"], "follow": true }
"shield_of_faith": { "effect": "faith-descend",    "target": "victim", "extras": ["faith-flash"],       "follow": true }
"bulwark":        { "effect": "bulwark-slam",      "target": "caster", "extras": ["bulwark-dust"],      "follow": true }
"evasion":        { "effect": "evasion-streak",    "target": "caster" }
"prayer":         { "effect": "prayer-blessing",   "target": "victim", "extras": ["prayer-ground-glow"], "follow": true }
```

### Backward Compatibility

Old presets (`buff-aura`, `shield-of-faith-aura`, `bulwark-fortify`, `evasion-blur`, `prayer-motes`) remain in `particle-presets.json` — they are no longer referenced by skill mappings but are preserved in case any other system references them.

---

## Tier 3: Multi-Emitter Composites (FUTURE)

### Goal

Leverage the existing `extras` system to create richer multi-layered effects by combining 2–3 emitters per skill cast.

### Ideas

- **Layered blending** — one emitter with `source-over` for solid base + one emitter with `lighter` for glowing highlights
- **Phased timing** — use `loopDuration` or staggered durations so extras fire slightly after the main effect
- **Ring + burst combos** — ground ring expanding outward + focused burst at center
- **Trail effects on buffs** — when a buffed unit moves, brief trail particles could emit from their last position (would require engine changes)

### Required Engine Changes (if pursuing)

- **Staggered extras** — add optional `delay` field to extras (fire after N seconds instead of simultaneously)
- **Composite presets** — a meta-preset that references multiple sub-presets with timing/offset data
- **Movement trails** — emit particles at the *previous* position when a unit moves between tiles

---

## Reference: Buff Types in `active_buffs`

| `type` value | Source Skills | Effect | Duration |
|---|---|---|---|
| `buff` | War Cry, Shield of Faith, Bulwark | Stat modifier (damage mult, armor) | 2–4 turns |
| `shield_charges` | Ward | Reflect damage charges | 6 turns |
| `evasion` | Evasion | Dodge charges | 4 turns |
| `hot` | Prayer | Heal per tick | 4 turns |
| `taunt` | Taunt | Force targeting | 2 turns |
| `detection` | Divine Sense | Reveal enemies (no visible aura) | 4 turns |
| `dot` | Wither, Venom Gaze | Damage per tick (debuff — handled separately) | 3–4 turns |
| `stun` | Shield Bash | Cannot act (CC — handled by `cc_status`) | 1 turn |
| `slow` | Crippling Shot | Cannot move (CC — handled by `cc_status`) | 2 turns |
