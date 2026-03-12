# Phase 14 — Visual Feedback & Combat Clarity

**Created:** February 28, 2026  
**Status:** In Progress — 14A complete, 14B complete, 14C complete, 14D complete, 14E complete, 14F complete, 14G complete (core system + visibility tuning pass)  
**Previous:** Phase 13 (Path Forward — Cleanup Pass) · 1,659+ tests passing · 0 failures

---

## The Problem

The game has 23 skills, 5 playable classes, 22 enemy types, active buffs/debuffs (DoTs, HoTs, stuns, slows, evasion, wards, taunts), and multi-party dungeon combat — but the player's primary feedback channel beyond the combat log is a handful of particle effects and damage floaters. When 8+ units are acting simultaneously, the screen shows shapes moving and HP bars changing with little visual explanation of *what actually happened*.

### Current Visual Feedback Inventory

| System | Coverage | Notes |
|--------|----------|-------|
| **Particle effects** | 12 of 23 skills mapped | 11 skills fire nothing |
| **Damage floaters** | Melee, ranged, skill damage, heals | No DoT tick, HoT tick, miss, dodge, stun, or block floaters |
| **Unit overlays** | Buff icons, stance indicators, HP bars | No stun/slow/CC visual on the unit itself |
| **Combat log** | Full coverage | Scrollable text — invisible during fast combat |
| **Unused presets** | 5 authored but never triggered | `poison-cloud`, `fire-blast`, `ice-shard`, `critical-hit`, `block` |

### Audit: Skill → Particle Mapping

**12 skills WITH particle effects:**

| Skill | Preset | Target |
|-------|--------|--------|
| `heal` | `heal-pulse` | victim (follow) |
| `double_strike` | `double-slash` | victim |
| `power_shot` | `power-shot-impact` | victim |
| `war_cry` | `buff-aura` | caster (follow) |
| `shadow_step` | `dark-bolt` + `portal-swirl` | destination + caster |
| `wither` | `wither-curse` | victim (follow) |
| `ward` | `ward-barrier` | caster (follow) |
| `divine_sense` | `divine-pulse` | caster |
| `rebuke` | `holy-smite` | victim |
| `shield_of_faith` | `shield-of-faith-aura` | victim (follow) |
| `exorcism` | `exorcism-flare` | victim (loop 2s) |
| `prayer` | `prayer-motes` | victim (follow) |

**11 skills WITHOUT particle effects:**

| Skill | Type | Classes/Enemies |
|-------|------|-----------------|
| `taunt` | AoE CC (self-target) | Crusader |
| `shield_bash` | Melee + Stun | Crusader, Undead Knight |
| `holy_ground` | AoE Heal | Crusader |
| `bulwark` | Self Armor Buff | Crusader, Undead Knight, Construct Guardian |
| `volley` | Ground AoE Damage | Ranger |
| `evasion` | Self Dodge Buff | Ranger, Skeleton |
| `crippling_shot` | Ranged + Slow | Ranger |
| `soul_reap` | Ranged Nuke | Reaper, Necromancer |
| `venom_gaze` | Ranged DoT | Medusa |
| `auto_attack_melee` | Basic melee | (covered by combat `attack` mapping) |
| `auto_attack_ranged` | Basic ranged | (covered by combat `ranged_attack` mapping) |

**5 existing presets never triggered:**

| Preset | Tags | Particle Style |
|--------|------|----------------|
| `poison-cloud` | combat | Green toxic cloud |
| `fire-blast` | combat | Orange/red explosion |
| `ice-shard` | combat | Blue crystalline burst |
| `critical-hit` | combat, critical | Star-shaped gold burst (30 particles) |
| `block` | combat, defense | Blue/white square sparks |

**3 combat mappings:**
- `attack` → `melee-hit` (+ `blood-splatter` extra) on victim
- `ranged_attack` → `ranged-hit` on victim
- `kill` → `death-burst` on victim

---

## Plan Overview

| Priority | Feature | Effort | Impact |
|----------|---------|--------|--------|
| **14A** | New particle presets for 9 unmapped skills | Medium | High — every skill gets visual identity | **COMPLETE** |
| **14B** | Map all skills in `particle-effects.json` | Trivial | High — activates 14A presets | **COMPLETE** |
| **14C** | DoT/HoT tick floaters | Small | High — explains mystery HP changes | **COMPLETE** |
| **14D** | Miss / Dodge / Blocked floaters | Small | Medium — explains failed attacks | **COMPLETE** |
| **14E** | Stun & Slow visual overlays on units | Small | High — CC states are invisible today | **COMPLETE** |
| **14F** | Critical / overkill hit emphasis | Small | Medium — big hits feel impactful | **COMPLETE** |
| **14G** | Ranged projectile travel system | Medium-Large | High — connects attacker to victim visually | **COMPLETE** |
| **14H** | Persistent status effect overlays | Medium | Medium — ongoing buffs/debuffs stay visible |
| **14I** | AoE ground indicators on resolution | Small | Medium — AoE skills show affected area |

---

## Priority 14A — New Particle Presets for Unmapped Skills

*Create 9 new presets in `client/public/particle-presets.json`. Each should have a distinct visual identity matching the skill's fantasy.*

**Note:** `auto_attack_melee` and `auto_attack_ranged` are already covered by the combat-level `attack` and `ranged_attack` mappings — they don't need separate skill presets.

### 14A-1: `taunt-shockwave`
- **Skill:** Taunt (Crusader) — force nearby enemies to target you
- **Fantasy:** Red intimidation wave rippling outward
- **Design:** Ring-shaped burst expanding from caster. Red/orange particles in a ring spawn pattern, expanding outward over ~0.5s. Medium burst count (20). Gravity: none. Particles fade from bright red → dark red.
- **Shape:** circle, spawnShape: ring, expanding outward
- **Color gradient:** `#ff4444` → `#aa2222` → `#440000`
- **Duration:** 0.5s, non-looping

### 14A-2: `shield-bash-impact`
- **Skill:** Shield Bash (Crusader, Undead Knight) — melee damage + stun
- **Fantasy:** Metallic shield slam with sparks
- **Design:** Directional burst toward victim. Metallic white/silver/blue sparks, heavy gravity to feel weighty. Short burst (12 particles). Square particle shape for metallic feel.
- **Shape:** square, spawnShape: point
- **Color gradient:** `#ffffff` → `#aaccff` → `#4466aa` → `#222244`
- **Duration:** 0.3s, non-looping
- **Extras:** Could pair with the existing `block` preset for the stun "stars" effect on victim

### 14A-3: `holy-ground-ring`
- **Skill:** Holy Ground (Crusader) — AoE heal around caster
- **Fantasy:** Golden consecrated ground expanding outward
- **Design:** Ring-expanding golden particles from caster center. Gentle upward drift. Large ring spawnRadius matching the 1-tile AoE. Warm gold/white gradient. Medium burst (25).
- **Shape:** circle, spawnShape: ring (large radius ~24px)
- **Color gradient:** `#ffffff` → `#ffee88` → `#ddaa33` → `#664400`
- **Duration:** 0.6s, non-looping
- **blendMode:** lighter

### 14A-4: `bulwark-fortify`
- **Skill:** Bulwark (Crusader, Undead Knight, Construct Guardian) — self armor buff
- **Fantasy:** Stone/earth shielding aura locking into place
- **Design:** Particles rise from ground around caster, then slow/stop. Earthy brown/grey/slate colors. Low speed, high friction — particles feel heavy and solid. Square shapes for a "stone block" feel.
- **Shape:** square, spawnShape: circle (small radius)
- **Color gradient:** `#ccccbb` → `#887766` → `#554433` → `#221100`
- **Duration:** 0.5s, non-looping
- **Gravity:** slight downward to feel grounded

### 14A-5: `volley-rain`
- **Skill:** Volley (Ranger) — AoE rain of arrows on target area
- **Fantasy:** Arrows falling from above onto the target zone
- **Design:** Particles spawn above the target area and fall downward with strong gravity. Narrow downward angle (250°-290°). Brown/wood colored with white tips. Elongated or default circle shape. High speed + gravity for "falling" feel. Spread over the AoE radius.
- **Shape:** circle (small, elongated feel from speed), spawnShape: circle (radius ~20px for AoE coverage)
- **Angle:** 250°–290° (mostly downward)
- **Color gradient:** `#ffffff` → `#ddcc88` → `#886644` → `#332211`
- **Duration:** 0.4s, non-looping
- **Gravity:** `{ x: 0, y: 200 }` — heavy downward pull
- **burstCount:** 20

### 14A-6: `evasion-blur`
- **Skill:** Evasion (Ranger, Skeleton) — dodge next 2 attacks
- **Fantasy:** Wispy afterimage / speed blur around the unit
- **Design:** Fast outward particles with high friction, creating a brief "whoosh" around the caster. Light grey/cyan/white wisps. Very short lifetime for a quick blur feel. Low particle count (10) but fast speed.
- **Shape:** circle, spawnShape: ring (small radius ~6px)
- **Color gradient:** `#ffffff` → `#aaeeff` → `#4499bb` → transparent
- **Duration:** 0.35s, non-looping
- **friction:** 0.06 (high)
- **alpha:** 0.8 → 0

### 14A-7: `crippling-shot-impact`
- **Skill:** Crippling Shot (Ranger) — ranged damage + slow
- **Fantasy:** Arrow strike that freezes/chains the target
- **Design:** Two-layer effect. Primary: icy blue impact burst (like `ranged-hit` but cold-colored). Pair with `ice-shard` as an extra for the "frozen" feel on victim.
- **Shape:** circle, spawnShape: point
- **Color gradient:** `#ffffff` → `#88ddff` → `#4488cc` → `#223366`
- **Duration:** 0.3s, non-looping
- **Extras:** `ice-shard` (already exists)

### 14A-8: `soul-reap-rend`
- **Skill:** Soul Reap (Reaper, Necromancer) — devastating ranged dark magic
- **Fantasy:** Dark energy tearing the victim's soul
- **Design:** Dark purple/black particles spiral inward toward victim center (negative speed or inward angle), then burst outward. Two-phase feel achieved by a tight initial ring that collapses. Heavy burst count (25) for dramatic impact. Dark palette.
- **Shape:** circle + star mix, spawnShape: ring (radius ~12px)
- **Speed:** inward pull feel — spawn on ring, low/moderate speed inward, then gravity pulls down
- **Color gradient:** `#cc66ff` → `#8833cc` → `#441166` → `#110033`
- **Duration:** 0.5s, non-looping
- **blendMode:** lighter

### 14A-9: `venom-gaze-bolt`
- **Skill:** Venom Gaze (Medusa) — ranged poison DoT
- **Fantasy:** Serpentine toxic energy striking the target
- **Design:** Green/yellow poison burst on victim with lingering wisps. Similar structure to `wither-curse` but green-shifted for poison fantasy (distinct from wither's dark/necrotic purple). Moderate burst, some particles linger longer for a "cloud" feel.
- **Shape:** circle, spawnShape: circle (small radius)
- **Color gradient:** `#eeff44` → `#88cc22` → `#447711` → `#223300`
- **Duration:** 0.5s, non-looping
- **Some particles with longer lifetime (0.4-0.8s) for lingering cloud effect**

### Files Changed
- `client/public/particle-presets.json` — Add 9 new preset definitions

### Testing
- Visual verification in Particle Lab tool (`start-particle-lab.bat`)
- Each preset can be tested in isolation before wiring to game events

### Implementation Log (February 28, 2026)
- **Status:** COMPLETE
- Added all 9 presets to `client/public/particle-presets.json` (total presets: 32 → 41)
- Each preset follows established format with `name`, `version`, `duration`, `loop`, `tags`, `emitter`, and `particle` blocks
- Preset summary:
  - `taunt-shockwave` — 20-particle red ring burst, 0.5s, ring spawn expanding outward
  - `shield-bash-impact` — 12-particle metallic square sparks, 0.3s, directional burst with heavy gravity
  - `holy-ground-ring` — 25-particle golden ring, 0.6s, large ring spawnRadius (24px), blendMode lighter
  - `bulwark-fortify` — 15-particle earthy square stones, 0.5s, high friction, downward gravity
  - `volley-rain` — 20-particle arrow rain (line shape), 0.4s, heavy downward gravity (200), trails
  - `evasion-blur` — 10-particle fast cyan wisps, 0.35s, high friction (0.06), small ring spawn
  - `crippling-shot-impact` — 16-particle icy blue triangles, 0.3s, rotating shards
  - `soul-reap-rend` — 25-particle dark purple ring collapse, 0.5s, trails, blendMode lighter
  - `venom-gaze-bolt` — 18-particle green poison burst, 0.5s, lingering long-lifetime particles
- JSON validated — no parse errors

---

## Priority 14B — Wire All Skills in Effect Mapping

*Update `client/public/particle-effects.json` to map every skill to its preset. Zero code changes — pure JSON config.*

### New Mappings to Add

```json
{
  "skills": {
    "taunt":          { "effect": "taunt-shockwave",     "target": "caster" },
    "shield_bash":    { "effect": "shield-bash-impact",  "target": "victim", "extras": ["block"] },
    "holy_ground":    { "effect": "holy-ground-ring",    "target": "caster" },
    "bulwark":        { "effect": "bulwark-fortify",     "target": "caster", "follow": true },
    "volley":         { "effect": "volley-rain",         "target": "destination" },
    "evasion":        { "effect": "evasion-blur",        "target": "caster" },
    "crippling_shot": { "effect": "crippling-shot-impact", "target": "victim", "extras": ["ice-shard"] },
    "soul_reap":      { "effect": "soul-reap-rend",      "target": "victim" },
    "venom_gaze":     { "effect": "venom-gaze-bolt",     "target": "victim", "follow": true }
  }
}
```

### Mapping Design Decisions

| Skill | Target | Follow? | Extras | Rationale |
|-------|--------|---------|--------|-----------|
| `taunt` | caster | no | — | Shockwave emanates from the taunter |
| `shield_bash` | victim | no | `block` (stun stars) | Impact on the hit target + stun indicator |
| `holy_ground` | caster | no | — | AoE emanates from caster's position |
| `bulwark` | caster | yes | — | Armor aura follows the buffed unit |
| `volley` | destination | no | — | Arrows rain on the targeted ground tile |
| `evasion` | caster | no | — | Quick blur on self, doesn't need tracking |
| `crippling_shot` | victim | no | `ice-shard` | Impact + freeze effect on slowed target |
| `soul_reap` | victim | no | — | Dark magic detonates on the victim |
| `venom_gaze` | victim | yes | — | Poison lingers on the victim briefly |

### Files Changed
- `client/public/particle-effects.json` — Add 9 new entries to the `skills` section

### Result
- **23/23 skills** will have visual feedback (21 unique mappings + 2 auto-attacks covered by combat mappings)
- **All 5 previously unused presets** (`poison-cloud`, `fire-blast`, `ice-shard`, `critical-hit`, `block`) now have at least one trigger path

### Implementation Log (February 28, 2026)
- **Status:** COMPLETE
- Added all 9 skill mappings to the `skills` section of `client/public/particle-effects.json`
- Total skill mappings: 12 → 21 (+ 2 auto-attacks via combat section = 23/23 skills covered)
- Cross-validated: all 24 referenced preset names confirmed present in `particle-presets.json`
- Zero code changes — pure JSON config as designed
- Mapping summary:
  - `taunt` → `taunt-shockwave` on caster (red shockwave radiates from taunter)
  - `shield_bash` → `shield-bash-impact` on victim + `block` extra (metallic sparks + stun stars)
  - `holy_ground` → `holy-ground-ring` on caster (golden consecration ring)
  - `bulwark` → `bulwark-fortify` on caster, follow: true (earthy stone aura follows unit)
  - `volley` → `volley-rain` on destination (arrows rain on target area)
  - `evasion` → `evasion-blur` on caster (quick cyan speed blur)
  - `crippling_shot` → `crippling-shot-impact` on victim + `ice-shard` extra (icy impact + freeze)
  - `soul_reap` → `soul-reap-rend` on victim (dark purple soul tear)
  - `venom_gaze` → `venom-gaze-bolt` on victim, follow: true (green poison lingers on target)

---

## Priority 14C — DoT / HoT Tick Floaters

*When Wither/Venom Gaze/Prayer tick each turn, show floating numbers on the affected unit.*

### Current Behavior
- Server sends tick results as `action_type: 'skill'` with `damage_dealt` or `heal_amount` set
- The `combatReducer.js` floater logic already handles `skill` actions with `damage_dealt` and `heal_amount`
- **However**, buff tick results from `_resolve_cooldowns_and_buffs` use the `buff_id` as the `skill_id` — these may or may not be generating floaters depending on exact data shape
- Need to verify and ensure tick floaters are reliably generated

### Implementation

**In `client/src/context/reducers/combatReducer.js`:**

1. Verify that DoT tick action results (`skill_id: 'wither'`, `damage_dealt: 6`) flow through the existing `act.damage_dealt` floater branch
2. If not, add an explicit check: if `act.action_type === 'skill'` and `act.damage_dealt > 0`, always generate a floater regardless of other conditions
3. Use a distinct **DoT floater color** — muted purple `#aa66dd` instead of bright purple `#cc66ff` — so the player can distinguish "Wither was cast" from "Wither ticked"
4. For HoT ticks, use a softer green `#88ddaa` distinct from direct heal green `#44ff44`

### Floater Color Scheme (Updated)

| Event | Color | Text |
|-------|-------|------|
| Melee damage | `#ff4444` (red) | 14px bold | `-X` |
| Ranged damage | `#ffaa00` (orange) | 14px bold | `-X` |
| Skill damage (direct) | `#cc66ff` (bright purple) | 14px bold | `-X` |
| **DoT tick damage** | `#aa66dd` (muted purple) | 12px bold | `-X` |
| Kill blow | `#ff8800` (bright orange) | 14px bold | `-X` |
| Direct heal | `#44ff44` (bright green) | 14px bold | `+X` |
| **HoT tick heal** | `#88ddaa` (soft green) | 12px bold | `+X` |

### Files Changed
- `server/app/models/actions.py` — Added `is_tick: bool = False` field to `ActionResult`
- `server/app/core/turn_resolver.py` — Set `is_tick=True` on DoT damage and HoT heal tick results in `_resolve_cooldowns_and_buffs()`
- `client/src/context/reducers/combatReducer.js` — Check `act.is_tick` for distinct floater colors and log types; floaters carry `isTick` flag
- `client/src/canvas/overlayRenderer.js` — Tick floaters render at 12px (vs 14px direct) with gentler upward drift (20px vs 30px)
- `server/tests/test_skills_combat.py` — 5 new tests in `TestTickFloaterFlag` class

### Design Decisions
- **Explicit `is_tick` flag from the server** — avoids fragile client-side heuristics (e.g., guessing based on `skill_id` or `player_id === target_id`). The server _knows_ it's resolving a buff tick, so it tells the client directly.
- **Smaller font (12px vs 14px)** — creates visual hierarchy: direct skill casts are prominent, periodic ticks are ambient background information.
- **Gentler drift (20px vs 30px)** — tick floaters rise slower and shorter, giving them a softer "pulse" feel vs the snappy direct damage floaters.
- **Distinct colors within the same hue family** — DoT ticks (`#aa66dd` muted purple) are clearly related to skill damage (`#cc66ff` bright purple) but visually distinguishable. Same for HoT ticks (`#88ddaa` soft green) vs direct heals (`#44ff44` bright green).

### Floater Color Reference (Complete)

| Event | Color | Hex | Font | Visual Role |
|-------|-------|-----|------|-------------|
| Melee damage | Red | `#ff4444` | 14px bold | Physical hit |
| Ranged damage | Orange | `#ffaa00` | 14px bold | Ranged hit (arrow/projectile) |
| Skill damage (direct cast) | Bright purple | `#cc66ff` | 14px bold | Active spell cast damage |
| DoT tick damage | Muted purple | `#aa66dd` | 12px bold | Periodic poison/curse damage |
| Kill blow | Bright orange | `#ff8800` | 14px bold | Lethal hit (any source) |
| Direct heal | Bright green | `#44ff44` | 14px bold | Active heal spell |
| HoT tick heal | Soft green | `#88ddaa` | 12px bold | Periodic prayer/regen heal |

### Testing
- Manual: cast Wither on enemy, observe tick floaters each turn (muted purple, 12px, gentle drift)
- Manual: cast Prayer on ally, observe heal tick floaters each turn (soft green, 12px, gentle drift)
- Manual: verify direct Heal and direct skill damage still use bright colors and 14px font
- Unit tests: 5 new tests in `TestTickFloaterFlag` — all passing (1646 total, 0 failures)

### Implementation Log (February 28, 2026)
- **Status:** COMPLETE
- Added `is_tick: bool = False` to `ActionResult` Pydantic model
- Flagged DoT and HoT tick results with `is_tick=True` in `_resolve_cooldowns_and_buffs()`
- Updated `combatReducer.js` to check `act.is_tick`:
  - DoT ticks → muted purple `#aa66dd` + `logType: 'dot_damage'`
  - HoT ticks → soft green `#88ddaa` + `logType: 'hot_heal'`
  - Direct skill damage → bright purple `#cc66ff` (unchanged)
  - Direct heal → bright green `#44ff44` (unchanged)
- Updated `overlayRenderer.js` `drawDamageFloaters()`:
  - Tick floaters (`isTick: true`) render at 12px font, 20px drift height
  - Direct floaters render at 14px font, 30px drift height (unchanged)
- Added 5 new Python tests covering: DoT tick flag, HoT tick flag, direct skill no-flag, both ticks same turn, DoT kill death result
- **Test count: 1641 → 1646** (5 new, 0 failures)

---

## Priority 14D — Miss / Dodge / Blocked Floaters

*When an attack fails, show contextual floating text so the player knows what happened.*

### Current Behavior
- Failed attacks generate combat log entries with `logType: 'miss'`
- No floating text appears on the canvas — the attack simply doesn't appear to happen

### Implementation

**In `client/src/context/reducers/combatReducer.js`:**

Add floater generation for failed attack/skill actions:

| Condition | Floater Text | Color | Position |
|-----------|-------------|-------|----------|
| `act.success === false` and `act.action_type === 'attack'` or `'ranged_attack'` | `MISS` | `#999999` (grey) | Target position |
| `act.message` contains "dodged" or "evaded" | `DODGE` | `#66ccff` (cyan) | Target position |
| `act.message` contains "stunned" | `STUNNED` | `#ffcc00` (yellow) | Caster position |
| `act.message` contains "slowed" | `SLOWED` | `#6688ff` (blue) | Caster position |
| Ward reflect triggers | `REFLECT` | `#cc88ff` (purple) | Attacker position |

### Particle Trigger for Dodge

Add a new combat mapping for evasion dodge events:

```json
"combat": {
  "dodge": {
    "effect": "evasion-blur",
    "target": "victim"
  }
}
```

This reuses the `evasion-blur` preset from 14A-6. The `ParticleManager.processActions()` would need a small addition to detect dodge events and fire this.

### Files Changed
- `client/src/context/reducers/combatReducer.js` — Add miss/dodge/stun/slow/reflect floater cases
- `client/public/particle-effects.json` — Add `dodge` to combat section
- `client/src/canvas/particles/ParticleManager.js` — Detect dodge events in `processActions()`
- `client/src/canvas/overlayRenderer.js` — Status floaters render at 11px with black outline for readability
- `server/tests/test_skills_combat.py` — 6 new tests in `TestMissDodgeStunnedFloaterData` class

### Testing
- Manual: have Ranger use Evasion, then get attacked — verify DODGE floater + evasion-blur particle
- Manual: attack from max range or through door — verify MISS floater on out-of-range failures
- Manual: stun a unit with Shield Bash, then have it try to act — verify STUNNED floater
- Manual: Ward reflect on attacker — verify REFLECT floater
- Unit tests: 6 new tests covering: melee dodge (target_id + DODGED message), ranged dodge, stunned melee, stunned ranged, melee miss out-of-range, ward reflect result

### Implementation Log (February 28, 2026)
- **Status:** COMPLETE
- **combatReducer.js** — Added new floater generation block for failed actions (`!act.success`):
  - `DODGE` floater (cyan `#66ccff`) on dodge target when message contains "dodged" or "evaded"
  - `STUNNED` floater (yellow `#ffcc00`) on caster when message contains "stunned"
  - `SLOWED` floater (blue `#6688ff`) on caster when message contains "slowed"
  - `MISS` floater (grey `#999999`) on target for all other failed attacks
  - `REFLECT` floater (purple `#cc88ff`) on attacker for ward reflect (successful skill with "reflects" in message)
  - All status floaters carry `isStatus: true` flag for distinct rendering
  - Ward reflect case placed *before* the general `!act.success` check to avoid misclassifying it (ward reflect is `success: true`)
- **particle-effects.json** — Added `dodge` → `evasion-blur` mapping to `combat` section
- **ParticleManager.js** — Added dodge detection in `processActions()`: failed actions with "dodged"/"evaded" in message fire `evasion-blur` on the dodger via the new `combat.dodge` mapping
- **overlayRenderer.js** — Updated `drawDamageFloaters()` to handle `isStatus` floaters:
  - 11px font (vs 14px damage / 12px ticks) for clear visual hierarchy
  - 25px drift height (between tick 20px and direct 30px)
  - Black outline (`strokeText`) for readability against any background
- **test_skills_combat.py** — Added `TestMissDodgeStunnedFloaterData` class with 6 tests:
  - `test_melee_dodge_has_target_id_and_dodged_message` — melee dodge via evasion buff
  - `test_ranged_dodge_has_target_id_and_dodged_message` — ranged dodge via evasion buff
  - `test_stunned_melee_has_stunned_message` — stunned unit melee attempt
  - `test_stunned_ranged_has_stunned_message` — stunned unit ranged attempt
  - `test_melee_miss_out_of_range` — non-adjacent melee attack
  - `test_ward_reflect_generates_reflect_result` — ward shield reflect action
- **Test count: 1646 → 1652** (6 new, 0 failures)

### Floater Color Reference (Updated with 14D)

| Event | Text | Color | Hex | Font | Position |
|-------|------|-------|-----|------|----------|
| Melee damage | `-X` | Red | `#ff4444` | 14px bold | Target |
| Ranged damage | `-X` | Orange | `#ffaa00` | 14px bold | Target |
| Skill damage (direct) | `-X` | Bright purple | `#cc66ff` | 14px bold | Target |
| DoT tick damage | `-X` | Muted purple | `#aa66dd` | 12px bold | Target |
| Kill blow | `-X` | Bright orange | `#ff8800` | 14px bold | Target |
| Direct heal | `+X` | Bright green | `#44ff44` | 14px bold | Target |
| HoT tick heal | `+X` | Soft green | `#88ddaa` | 12px bold | Target |
| **MISS** | `MISS` | Grey | `#999999` | 11px bold + outline | Target |
| **DODGE** | `DODGE` | Cyan | `#66ccff` | 11px bold + outline | Target (dodger) |
| **STUNNED** | `STUNNED` | Yellow | `#ffcc00` | 11px bold + outline | Caster (stunned unit) |
| **SLOWED** | `SLOWED` | Blue | `#6688ff` | 11px bold + outline | Caster (slowed unit) |
| **REFLECT** | `REFLECT` | Purple | `#cc88ff` | 11px bold + outline | Attacker (reflected onto) |

---

## Priority 14E — Stun & Slow Visual Overlays

*Units affected by stun or slow should have a visible indicator on their sprite, not just in the combat log.*

### Current Behavior
- Stunned units have their `active_buffs` contain a `stun` entry, but no visual is drawn
- Slowed units have a `slow` buff entry, but no visual is drawn
- The player only knows a unit is CC'd by reading the combat log or noticing it didn't act

### Implementation

**In `client/src/canvas/unitRenderer.js`:**

Add a new `drawCrowdControlIndicators(ctx, x, y, activeBuffs, ox, oy)` function:

1. **Stun indicator:** Small spinning stars (⭑) orbiting above the unit's head. Draw 2-3 star characters rotating in a circle above the nameplate area. Yellow/gold color with pulsing alpha.

2. **Slow indicator:** Blue chains or frost overlay. Draw a subtle blue-tinted overlay on the unit tile, plus small ice crystal characters (❄) near the unit's feet. Blue/cyan color.

3. **Taunt indicator:** On enemies forced to target a specific unit, show a small red arrow (→) pointing toward the taunter. Red color.

**In `client/src/canvas/ArenaRenderer.js` `renderFrame()`:**

Call `drawCrowdControlIndicators()` for each visible unit that has stun/slow buffs in their `active_buffs` array.

### Visual Design

| CC State | Icon/Effect | Position | Color |
|----------|------------|----------|-------|
| Stunned | Rotating ⭑⭑⭑ | Above nameplate | `#ffcc00` gold, pulsing |
| Slowed | ❄ frost marks | At unit feet | `#6688ff` blue |
| Taunted | → arrow toward taunter | Below unit | `#ff4444` red |

### Files Changed
- `client/src/canvas/unitRenderer.js` — New `drawCrowdControlIndicators()` function + helpers (`_drawStunStars`, `_drawSlowFrost`, `_drawTauntIndicator`, `_drawStarShape`)
- `client/src/canvas/ArenaRenderer.js` — Import + call CC indicators in render loop after buff icons
- `client/src/canvas/particles/ParticleManager.js` — New CC status particle system: `_ccEmitters` map, `updateCCStatus()`, `_updateCCEmitters()`
- `client/src/components/Arena/Arena.jsx` — Wire `updateCCStatus()` into players/visibleTiles sync hook
- `client/public/particle-presets.json` — 2 new looping presets: `stun-stars`, `slow-frost` (total presets: 41 → 43)
- `client/public/particle-effects.json` — New `cc_status` section mapping stun/slow to looping particle presets
- `server/tests/test_skills_combat.py` — 7 new tests in `TestCCVisualOverlayData` class

### Testing
- Manual: Crusader uses Shield Bash on enemy → stunned stars appear for 1 turn
- Manual: Ranger uses Crippling Shot → slow frost appears for 2 turns
- Manual: Crusader uses Taunt → taunted enemies show red arrow
- Unit tests: 7 new tests covering: stun/slow/taunt buff presence, stun decrement, stun expiry, slow decrement, stunned action blocked with buff intact

### Implementation Log (February 28, 2026)
- **Status:** COMPLETE
- **Dual rendering approach:** CC indicators render via both canvas-drawn overlays (in `unitRenderer.js`) AND persistent particle effects (via `ParticleManager`). Canvas overlays provide crisp, always-visible indicators (rotating stars, frost marks, taunt exclamation). Particle effects add ambient visual flair on a separate overlay canvas.

#### Canvas CC Overlays (unitRenderer.js)
- **Stun:** 3 gold ⭑ stars orbiting above the unit's nameplate in a flattened ellipse. Stars are drawn as 5-pointed shapes (not font characters) for crisp rendering. Orbit speed: 2 rad/s, pulsing alpha 0.7–1.0.
- **Slow:** Blue tint overlay on the tile (`rgba(100,136,255,0.08–0.14)`) + dashed frost ring at unit's feet + 3 rotating ❄ crystal characters. Blue/cyan palette.
- **Taunt:** Red pulsing `!` exclamation below the unit with black stroke outline for readability + subtle red ring around the unit. Indicates forced targeting.
- All indicators use `Date.now()` for animation timing — no external animation state needed.
- Function signature: `drawCrowdControlIndicators(ctx, x, y, activeBuffs, isBoss)` — checks for `type === 'stun'`, `'slow'`, `'taunt'` in active_buffs.

#### Particle CC Effects (ParticleManager.js)
- New `cc_status` section in `particle-effects.json` maps buff types to looping presets
- `updateCCStatus(players, visibleTiles)` scans all visible players for CC buffs, creates looping emitters for new CC states, removes emitters when CC expires
- CC emitters tracked in `_ccEmitters` Map keyed by `${playerId}:${ccType}`
- Stun particle emitter positioned 12px above unit center; slow particle emitter at unit center
- `_updateCCEmitters()` runs each rAF frame to reposition emitters following their bound player

#### New Particle Presets
- **`stun-stars`** — Looping, 6 particles/sec, star-shaped, gold/yellow gradient (`#ffffff` → `#ffee55` → `#ffcc00` → `#996600`), ring spawn (10px radius), gentle upward drift, rotation 90–180°/s, blendMode lighter
- **`slow-frost`** — Looping, 5 particles/sec, triangle-shaped (ice crystals), blue gradient (`#ffffff` → `#aaddff` → `#6688ff` → `#223366`), circle spawn (12px radius), gentle upward drift, rotation 45–120°/s, blendMode lighter

#### Tests Added
- 7 new tests in `TestCCVisualOverlayData`:
  - `test_stun_buff_present_in_active_buffs` — stun type recognized, turns_remaining correct
  - `test_slow_buff_present_in_active_buffs` — slow type recognized, turns_remaining correct
  - `test_taunt_buff_present_in_active_buffs` — taunt type recognized, source_id preserved
  - `test_stun_buff_decrements_on_tick` — turns_remaining goes 2 → 1 after resolve_turn
  - `test_stun_buff_expires_after_final_tick` — turns_remaining=1 → removed after tick
  - `test_slow_buff_decrements_on_tick` — turns_remaining goes 3 → 2 after resolve_turn
  - `test_stunned_unit_action_blocked_with_buffs_intact` — attack blocked, stun buff still present for rendering
- **Test count: 1652 → 1659** (7 new, 0 failures)

---

## Priority 14F — Critical / Overkill Hit Emphasis

*Big hits should FEEL big. Use the existing `critical-hit` preset and amplify floater text.*

### Current Behavior
- The `critical-hit` preset exists (30 star-burst particles, gold/orange) but is never triggered
- All damage floaters use the same 14px font regardless of damage magnitude
- A 5-damage auto-attack looks the same as a 48-damage Soul Reap

### Implementation

**In `client/src/canvas/particles/ParticleManager.js` `processActions()`:**

Add a threshold check after firing the normal combat/skill effect:

```javascript
// Fire critical-hit preset for kills or high-damage hits
if (act.killed || (act.damage_dealt && act.damage_dealt >= HIGH_DAMAGE_THRESHOLD)) {
  const critMapping = { effect: 'critical-hit', target: 'victim' };
  this._fireEffect(critMapping, act, players);
}
```

`HIGH_DAMAGE_THRESHOLD` = ~25 (roughly 50% of a tanky unit's HP, tunable).

**In `client/src/canvas/overlayRenderer.js` `drawDamageFloaters()`:**

Scale font size based on damage magnitude:

| Damage | Font Size | Extra |
|--------|-----------|-------|
| 1–10 | 12px | — |
| 11–20 | 14px (current) | — |
| 21–30 | 16px bold | — |
| 31+ | 18px bold | Slight horizontal shake offset |
| Kill blow | 16px bold | `☠` prefix or suffix |

### Files Changed
- `client/src/canvas/particles/ParticleManager.js` — Fire `critical-hit` on big hits/kills
- `client/src/canvas/overlayRenderer.js` — Scale floater font size by damage magnitude
- `client/src/context/reducers/combatReducer.js` — Add `damageAmount` and `isKill` fields to damage floaters
- `server/tests/test_skills_combat.py` — 6 new tests in `TestCriticalOverkillHitData` class

### Testing
- Manual: War Cry + melee strike (2x damage) should trigger critical-hit particles
- Manual: Power Shot on low-armor target should show large floater text
- Visual: verify kill blows show death-burst + critical-hit layered
- Unit tests: 6 new tests covering: melee kill data shape, high-damage exceeds threshold, ranged kill data, skill damage carries damage_dealt, low damage carries damage_dealt, overkill has both killed and high damage

### Implementation Log (February 28, 2026)
- **Status:** COMPLETE
- **ParticleManager.js** — Added critical-hit particle trigger after the existing kill effect logic:
  - `HIGH_DAMAGE_THRESHOLD = 25` (roughly 50% of a tanky unit's HP, tunable)
  - If `act.damage_dealt >= 25` OR `act.killed`, fire the existing `critical-hit` preset on the victim
  - The `critical-hit` preset (30 star-burst particles, gold/orange) was already authored but never triggered — now activated
  - Fires in addition to normal combat/skill effects and the existing `death-burst` kill effect
- **combatReducer.js** — Added two new fields to all damage floater objects:
  - `damageAmount: act.damage_dealt` — raw damage number for the renderer to scale font size
  - `isKill: !!act.killed` — kill flag for skull prefix rendering
  - Added to both melee/ranged floaters and skill damage floaters
- **overlayRenderer.js** — Rewrote `drawDamageFloaters()` font scaling logic:
  - Status floaters (MISS, DODGE, etc.): 11px, 25px drift (unchanged from 14D)
  - Tick floaters (DoT/HoT): 12px, 20px drift (unchanged from 14C)
  - Damage by magnitude using `f.damageAmount`:
    - Kill blow: 16px bold + `☠` skull prefix + 35px drift
    - 31+ damage: 18px bold + horizontal shake oscillation (`sin(age * 0.03) * 2`) + 35px drift
    - 21–30 damage: 16px bold + 32px drift
    - 11–20 damage: 14px bold + 30px drift (matches previous default)
    - 1–10 damage: 12px + 28px drift
  - Big hits (16px+) and kill blows get black stroke outline (lineWidth 3) for emphasis and readability
  - Horizontal shake for 31+ damage decays with progress so it calms as the floater fades
  - Fallback for floaters without `damageAmount` (e.g., heals): 14px, 30px drift (unchanged)
- **test_skills_combat.py** — Added `TestCriticalOverkillHitData` class with 6 tests:
  - `test_melee_kill_has_killed_and_damage_dealt` — lethal melee has both `killed=True` and `damage_dealt > 0`
  - `test_high_damage_melee_exceeds_threshold` — War Cry buffed melee produces `damage_dealt >= 25`
  - `test_ranged_kill_has_killed_and_damage` — lethal ranged has `killed=True` and `damage_dealt`
  - `test_skill_damage_has_damage_dealt_field` — Power Shot carries `damage_dealt` for font scaling
  - `test_low_damage_still_has_damage_dealt` — weak attack still carries `damage_dealt` (low tier)
  - `test_overkill_has_both_killed_and_high_damage` — massive overkill has both flags for layered effects
- **Test count: 1659 → 1665** (6 new, 0 failures)

### Floater Font Scaling Reference (14F)

| Damage Range | Font Size | Extra Visual | Drift Height |
|-------------|-----------|-------------|-------------|
| Kill blow (any) | 16px bold | ☠ skull prefix + outline | 35px |
| 31+ damage | 18px bold | Horizontal shake + outline | 35px |
| 21–30 damage | 16px bold | Black outline | 32px |
| 11–20 damage | 14px bold | — | 30px |
| 1–10 damage | 12px | — | 28px |
| DoT/HoT tick | 12px | — | 20px |
| Status (MISS, etc.) | 11px bold | Black outline | 25px |

### 14F Addendum — Universal Black Outline on All Floaters (February 28, 2026)

**Status:** COMPLETE

**Problem:** The 14F implementation added black `strokeText` outlines only to big hits (fontSize >= 16) and status text (MISS, DODGE, etc.). Smaller damage floaters (1-20 melee/ranged/skill damage), DoT/HoT ticks, and heal floaters had no outline — making them harder to read against busy backgrounds (grimdark tiles, overlapping unit sprites, particle effects). The contrast between outlined and non-outlined floaters was night-and-day once noticed.

**Solution:** Extended the black `strokeText` outline to **every** floater in `drawDamageFloaters()`, with `lineWidth` scaled by font size tier:

| Font Size | lineWidth | Floater Types |
|-----------|-----------|---------------|
| 16px+ | 3 | Kill blows, 21+ damage, 31+ massive hits |
| 14px | 2.5 | 11-20 damage, direct heals (no damageAmount) |
| 11-12px | 2 | 1-10 damage, DoT ticks, HoT ticks, status text |

Added `lineJoin: 'round'` for smooth outline corners on all text — prevents jagged miter points on characters like `M`, `W`, `☠`.

**Change:** Single edit in `overlayRenderer.js` `drawDamageFloaters()` — replaced the conditional `if (isStatus || fontSize >= 16)` outline block with an unconditional outline that fires for every floater. The `ctx.font` and `ctx.textAlign` are now set once instead of potentially twice.

**Before (14F):**
```javascript
// Only status and big hits got outlines
if (isStatus || fontSize >= 16) {
  ctx.strokeStyle = '#000000';
  ctx.lineWidth = isStatus ? 2.5 : 3;
  ctx.strokeText(displayText, cx, cy);
}
```

**After (14F addendum):**
```javascript
// ALL floaters get outlines — lineWidth scales with font size
ctx.strokeStyle = '#000000';
ctx.lineWidth = fontSize >= 16 ? 3 : (fontSize >= 14 ? 2.5 : 2);
ctx.lineJoin = 'round';
ctx.strokeText(displayText, cx, cy);
```

**Floaters affected by this change (previously had NO outline):**

| Floater | Color | Font | Now Has |
|---------|-------|------|---------|
| Melee damage 1-10 | Red `#ff4444` | 12px | 2px outline |
| Melee damage 11-20 | Red `#ff4444` | 14px | 2.5px outline |
| Ranged damage 1-10 | Orange `#ffaa00` | 12px | 2px outline |
| Ranged damage 11-20 | Orange `#ffaa00` | 14px | 2.5px outline |
| Skill damage 1-10 | Purple `#cc66ff` | 12px | 2px outline |
| Skill damage 11-20 | Purple `#cc66ff` | 14px | 2.5px outline |
| DoT tick damage | Muted purple `#aa66dd` | 12px | 2px outline |
| HoT tick heal | Soft green `#88ddaa` | 12px | 2px outline |
| Direct heal | Bright green `#44ff44` | 14px | 2.5px outline |

**Files Changed:**
- `client/src/canvas/overlayRenderer.js` — `drawDamageFloaters()`: unconditional black outline on all floaters, scaled lineWidth, added lineJoin round

**No test changes needed** — this is a pure rendering-only change with no data shape changes.

### Updated Floater Visual Reference (Complete — Post-14F Addendum)

| Event | Text | Color | Font | Outline | Position |
|-------|------|-------|------|---------|----------|
| Melee 1-10 | `-X` | Red `#ff4444` | 12px bold | 2px black | Target |
| Melee 11-20 | `-X` | Red `#ff4444` | 14px bold | 2.5px black | Target |
| Melee 21-30 | `-X` | Red `#ff4444` | 16px bold | 3px black | Target |
| Melee 31+ | `-X` | Red `#ff4444` | 18px bold | 3px black + shake | Target |
| Ranged 1-10 | `-X` | Orange `#ffaa00` | 12px bold | 2px black | Target |
| Ranged 11-20 | `-X` | Orange `#ffaa00` | 14px bold | 2.5px black | Target |
| Ranged 21-30 | `-X` | Orange `#ffaa00` | 16px bold | 3px black | Target |
| Ranged 31+ | `-X` | Orange `#ffaa00` | 18px bold | 3px black + shake | Target |
| Skill damage 1-10 | `-X` | Purple `#cc66ff` | 12px bold | 2px black | Target |
| Skill damage 11-20 | `-X` | Purple `#cc66ff` | 14px bold | 2.5px black | Target |
| Skill damage 21-30 | `-X` | Purple `#cc66ff` | 16px bold | 3px black | Target |
| Skill damage 31+ | `-X` | Purple `#cc66ff` | 18px bold | 3px black + shake | Target |
| Kill blow | `☠ -X` | Bright orange `#ff8800` | 16px bold | 3px black | Target |
| DoT tick | `-X` | Muted purple `#aa66dd` | 12px bold | 2px black | Target |
| HoT tick | `+X` | Soft green `#88ddaa` | 12px bold | 2px black | Target |
| Direct heal | `+X` | Bright green `#44ff44` | 14px bold | 2.5px black | Target |
| MISS | `MISS` | Grey `#999999` | 11px bold | 2px black | Target |
| DODGE | `DODGE` | Cyan `#66ccff` | 11px bold | 2px black | Dodger |
| STUNNED | `STUNNED` | Yellow `#ffcc00` | 11px bold | 2px black | Caster |
| SLOWED | `SLOWED` | Blue `#6688ff` | 11px bold | 2px black | Caster |
| REFLECT | `REFLECT` | Purple `#cc88ff` | 11px bold | 2px black | Attacker |

---

## Priority 14G — Ranged Projectile Travel

*Show a visual projectile traveling from caster to victim for ranged attacks and spells.*

### Current Behavior
- All particle effects spawn at a fixed point (victim or caster position)
- A Ranger firing Power Shot: particles appear on the victim with no visual link to the Ranger
- Rebuke, Exorcism, Soul Reap, Wither, Venom Gaze — all fire at the victim with no travel

### Implementation

**New class: `client/src/canvas/particles/ParticleProjectile.js`**

A lightweight projectile that moves a small particle cluster from point A to point B:

```
class ParticleProjectile {
  constructor(engine, presetName, fromX, fromY, toX, toY, speed, onArrive)
  update(dt)  — move toward target, emit trail particles
  isComplete  — true when arrived
}
```

- **Travel time:** ~0.2–0.4s depending on distance (configurable per mapping)
- **Trail:** Small particles emitted along the path, matching the skill's color theme
- **On arrival:** Fire the normal impact effect at the destination

**New field in `particle-effects.json` mappings:**

```json
"power_shot": {
  "effect": "power-shot-impact",
  "target": "victim",
  "projectile": {
    "trail": "ranged-trail",
    "speed": 400
  }
}
```

When `projectile` is present, `ParticleManager` creates a `ParticleProjectile` from caster → victim, and only fires the impact `effect` when the projectile arrives.

**New presets needed:**

| Trail Preset | Color | Used By |
|-------------|-------|---------|
| `arrow-trail` | Brown/white | Auto ranged, Power Shot, Crippling Shot, Volley |
| `holy-bolt-trail` | Gold/white | Rebuke, Exorcism |
| `dark-bolt-trail` | Purple/black | Wither, Soul Reap, Venom Gaze |

### Applicable Skills

| Skill | Trail | Speed | Impact |
|-------|-------|-------|--------|
| `auto_attack_ranged` | `arrow-trail` | 520 | `ranged-hit` |
| `power_shot` | `arrow-trail` | 700 | `power-shot-impact` |
| `crippling_shot` | `arrow-trail` | 520 | `crippling-shot-impact` |
| `rebuke` | `holy-bolt-trail` | 950 | `holy-smite` |
| `exorcism` | `holy-bolt-trail` | 850 | `exorcism-flare` |
| `soul_reap` | `dark-bolt-trail` | 1000 | `soul-reap-rend` |
| `wither` | `dark-bolt-trail` | 600 | `wither-curse` |
| `venom_gaze` | `dark-bolt-trail` | 650 | `venom-gaze-bolt` |

### Files Changed
- `client/src/canvas/particles/ParticleProjectile.js` — New file
- `client/src/canvas/particles/ParticleManager.js` — Handle `projectile` field in mappings
- `client/public/particle-presets.json` — Add 3 trail presets
- `client/public/particle-effects.json` — Add `projectile` config to ranged skill mappings

### Testing
- Manual: ranged auto-attack → arrow visibly travels from Ranger to target
- Manual: Rebuke → golden bolt crosses the screen to victim
- Verify projectile travel time scales reasonably with distance
- Edge case: caster and victim on same tile (min travel time)

### Implementation Log (February 28, 2026)
- **Status:** COMPLETE — Core system implemented + visibility bug fix & preset tuning pass

#### Architecture: Direct Pixel-Space Interpolation
- Projectiles travel in a **straight pixel-space line** from caster center → victim center using `lerp()`. They never snap to the tile grid.
- An optional **parabolic arc** (`arc` param, 0–1) adds vertical offset via `sin(progress * PI)`. Physical arrows get gentle arcs (0.15–0.2), magic bolts fly flat (0–0.08).
- Travel time is derived from pixel distance ÷ speed (px/s), with a minimum duration of 0.06s (3–4 frames) for same-tile edge cases.
- On arrival, the projectile fires a callback that triggers the impact effect + extras at the destination — identical to pre-14G behavior.

#### New File: `ParticleProjectile.js`
- Lightweight class: constructor takes `{trailPreset, fromX, fromY, toX, toY, speed, arc, onArrive}`
- `update(dt)` — advances progress 0→1, interpolates X linearly, interpolates Y linearly + parabolic arc offset, repositions trail emitter via `moveTo()`
- `isDead` — true when arrived AND trail emitter particles have all died (clean cleanup)
- `forceComplete()` — immediate completion for destroy/cleanup scenarios
- Trail emitter is created as a looping continuous emitter; stopped on arrival so remaining trail particles fade naturally

#### ParticleManager.js Changes
- **Import** `ParticleProjectile` from new file
- **Constructor:** Added `_projectiles = []` array for active in-flight projectiles
- **`_tick()`:** Added `_updateProjectiles(dt)` call in the rAF loop (after CC emitters, before engine.update)
- **`_fireEffect()`:** Refactored — if mapping has `projectile.trail`, calls `_launchProjectile()` which defers impact; otherwise calls `_fireImpact()` for immediate fire (preserves all existing non-projectile behavior)
- **`_launchProjectile()`:** Resolves caster position, creates `ParticleProjectile`, pushes to `_projectiles` array. Falls back to immediate impact if caster position unavailable.
- **`_fireImpact()`:** Extracted from old `_fireEffect()` — handles emitter creation, loop duration, follow tracking, and extras. Called immediately for non-projectile effects, or as the `onArrive` callback for projectiles.
- **`_updateProjectiles(dt)`:** Iterates active projectiles, calls `update(dt)`, removes dead ones (reverse loop for safe splice)
- **`destroy()`:** Force-completes all in-flight projectiles before clearing

#### New Trail Presets (3 added to `particle-presets.json`, total presets: 43 → 46)
- **`arrow-trail`** — 30 particles/sec continuous, brown/white gradient (`#ffffff` → `#ddcc88` → `#886644` → `#332211`), circle shape, 0.08–0.18s lifetime, slight downward gravity (15), `source-over` blend for opaque arrow feel
- **`holy-bolt-trail`** — 35 particles/sec continuous, gold/white gradient (`#ffffff` → `#ffee88` → `#ddaa33` → `#664400`), circle shape, 0.1–0.2s lifetime, slight upward gravity (-5), `lighter` blend for glowing holy bolt
- **`dark-bolt-trail`** — 30 particles/sec continuous, purple/black gradient (`#cc66ff` → `#8833cc` → `#441166` → `#110033`), circle shape, 0.1–0.22s lifetime, upward gravity (-8) for creepy drift, `lighter` blend

#### Projectile Config per Skill (8 mappings updated in `particle-effects.json`)

| Skill | Trail | Speed (px/s) | Arc | Visual Feel |
|-------|-------|-------------|-----|-------------|
| `ranged_attack` (combat) | `arrow-trail` | 520 | 0.10 | Standard arrow, gentle arc |
| `power_shot` | `arrow-trail` | 700 | 0.12 | Fast powerful arrow, subtle arc |
| `crippling_shot` | `arrow-trail` | 520 | 0.08 | Standard arrow + ice impact |
| `rebuke` | `holy-bolt-trail` | 950 | 0 | Snappy divine bolt |
| `exorcism` | `holy-bolt-trail` | 850 | 0 | Fast holy beam |
| `soul_reap` | `dark-bolt-trail` | 1000 | 0 | Near-instant dark devastation |
| `wither` | `dark-bolt-trail` | 600 | 0 | Purposeful dark curse bolt |
| `venom_gaze` | `dark-bolt-trail` | 650 | 0 | Quick poison eye beam |

#### Design Decisions
- **Pixel-space interpolation, never tile-space** — avoids jittery grid-snapping on diagonals. Projectiles look smooth regardless of angle.
- **Arc as a fraction of distance** — `arcOffset = -arc * totalDistance * sin(progress * PI)`. Negative offset = upward on canvas. Short-range shots arc less in absolute pixels; long-range shots arc more. Feels natural.
- **Configurable per skill via JSON** — no code changes needed to tune speeds, arcs, or trail presets. Each skill gets its own flight personality.
- **Impact fires on arrival callback** — the existing follow, extras, and loopDuration logic all work unchanged because `_fireImpact()` is the same code path that `_fireEffect()` used to run directly.
- **Graceful fallback** — if caster position can't be resolved (e.g., caster died mid-resolution), falls back to immediate impact at target. Game never breaks.
- **Minimum duration floor (0.06s)** — prevents division-by-zero or invisible projectiles when caster and victim are on the same tile.

#### Remaining Work
- [x] Visual testing in-game — verify trail appearance, arc feel, impact timing → **14G Addendum below**
- [x] Tune speeds/arcs per skill if needed after visual review → **14G Addendum below**
- [ ] Consider whether Volley (AoE arrow rain) should also get projectiles (currently impact-only since it's a barrage from the sky)
- [ ] Edge case testing: max range (7 tiles), adjacent tile (1 tile), same tile, caster dies mid-flight

### 14G Addendum — Projectile Visibility Bug Fix & Preset Tuning (February 28, 2026)

**Status:** COMPLETE

#### Problem: Projectiles appear as small white balls with no visible trail

During visual testing, projectiles from all ranged attacks and spells appeared as tiny white dots with no discernible trail or color. Three compounding issues were identified:

**Bug 1: `rate` vs `spawnRate` field name mismatch in Emitter.js**

The `Emitter` constructor reads `em.spawnRate` to set the continuous emission rate, but all 18 new presets (14G trail/head presets + 14E CC presets) used `em.rate` — a field the Emitter completely ignored. This caused every new continuous preset to fall back to the default rate of 30 particles/sec regardless of its intended rate.

Impact:
- Trail presets that wanted 25–55 particles/sec all got 30 — usually close enough but imprecise
- **stun-stars** wanted 6/sec, got **30/sec** (5× too many — overwhelming blur instead of gentle orbiting stars)
- **slow-frost** wanted 5/sec, got **30/sec** (6× too many — same problem)
- The older continuous presets (heal-pulse, buff-aura, ward-barrier, etc.) all used `spawnRate` and were unaffected

Root cause: the 14G and 14E presets were authored with a different field name (`rate`) than what the existing engine code expected (`spawnRate`). Both names are reasonable; the code only checked one.

**Bug 2: Head presets had invisibly short lifetimes**

The projectile "head" (the bright tip of the projectile) used particle lifetimes of 0.03–0.09 seconds with sizes of 1.5–3 pixels. At 60fps, each particle lived for only 2–5 frames. With emission rates producing ~1–2 alive particles at any moment, the head was a barely-perceptible flickering dot.

**Bug 3: Trail presets were too faint**

Trail particles had lifetimes of 0.06–0.22 seconds at 1.5–4.5 pixel sizes, producing only ~3–5 alive particles at any moment. Combined with gradients that started at pure white (`#ffffff`) and didn't reach their characteristic color until 30% through the lifetime — but particles often died before reaching that point — everything looked like tiny white specks.

**Bug 4: soul-reap-trail had a green gradient (copy-paste error)**

The `soul-reap-trail` preset (for the Reaper's dark purple Soul Reap skill) had a green gradient (`#88ff88` → `#44aa44` → `#224422` → `#0a0a0a`). This was clearly a copy-paste from the venom-trail preset. Fixed to purple (`#dd88ff` → `#aa55dd` → `#662299` → `#220044`).

#### Fix 1: Emitter.js — Read both `spawnRate` and `rate` fields

**File:** `client/src/canvas/particles/Emitter.js`

```javascript
// Before (line 36 — constructor):
this.spawnRate = em.spawnRate || 30;

// After:
this.spawnRate = em.spawnRate || em.rate || 30;

// Same fix applied in applyPreset() (line 217)
```

This is backwards-compatible: existing presets using `spawnRate` still work, and new presets using `rate` now also work. Both field names resolve correctly.

#### Fix 2: Trail presets — increased lifetimes, sizes, and shifted gradients

All 10 trail presets were tuned for visibility:

| Preset | Rate | Lifetime | Size (start) | Avg Alive | Gradient Start |
|--------|------|----------|-------------|-----------|----------------|
| `arrow-trail` | 30→**40** | 0.08–0.18→**0.15–0.35** | 1.5–3→**2.5–4.5** | 3.9→**10.0** | `#fff`→`#ffffcc` |
| `power-shot-trail` | 40→**50** | 0.1–0.22→**0.15–0.3** | 2–4→**3–5** | 6.4→**11.2** | `#fff`→`#ffffaa` |
| `crip-shot-trail` | 35→**45** | 0.08–0.2→**0.15–0.3** | 1.5–3→**2.5–4** | 4.9→**10.1** | `#fff`→`#eeffff` |
| `rebuke-trail` | 40→**50** | 0.06–0.14→**0.12–0.25** | 1.5–3→**2.5–4** | 4.0→**9.3** | `#fff`→`#ffffcc` |
| `exorcism-trail` | 45→**55** | 0.12–0.25→**0.15–0.3** | 2.5–5 (kept) | 8.3→**12.4** | shifted to 0.1 |
| `soul-reap-trail` | 35→**45** | 0.1–0.22→**0.15–0.3** | 2–4→**2.5–5** | 5.6→**10.1** | green→**purple** |
| `wither-trail` | 25→**35** | 0.15–0.3→**0.2–0.4** | 1.5–3.5→**2.5–4.5** | 5.6→**10.5** | shifted to 0.12 |
| `venom-trail` | 30→**40** | 0.1–0.22→**0.15–0.3** | 2–4→**2.5–5** | 4.8→**9.0** | shifted to 0.12 |
| `dark-bolt-trail` | 30→**40** | 0.1–0.22→**0.15–0.3** | 2–4.5→**3–5.5** | 4.8→**9.0** | `#cc66ff`→`#ee88ff` |
| `holy-bolt-trail` | 35→**45** | 0.1–0.2→**0.15–0.3** | 2–4→**3–5** | 5.3→**10.1** | shifted to 0.12 |

Gradient design changes:
- **Removed pure white starts** — replaced `#ffffff` at stop 0 with tinted whites (`#ffffcc`, `#ffffaa`, `#eeffff`, etc.) that immediately hint at the skill's color family
- **Shifted color stops earlier** — characteristic colors now appear at stop 0.12–0.15 instead of 0.25–0.3, so even short-lived particles show their identity color

#### Fix 3: Head presets — increased lifetimes and sizes for visible tips

All 6 head presets were tuned:

| Preset | Rate | Lifetime | Size (start) | Avg Alive |
|--------|------|----------|-------------|-----------|
| `arrow-head` | 45→**55** | 0.03–0.06→**0.06–0.12** | 1.5–2.5→**3–5** | 1.4→**5.0** |
| `power-shot-head` | 50→**60** | 0.04–0.08→**0.07–0.14** | 2–3→**3.5–5.5** | 1.8→**6.3** |
| `ice-arrow-head` | 45→**55** | 0.03–0.07→**0.06–0.12** | 2–3→**3–5** | 1.5→**5.0** |
| `holy-head` | 50→**60** | 0.04–0.08→**0.07–0.14** | 1.5–2.5→**3–5** | 1.8→**6.3** |
| `dark-head` | 40→**50** | 0.05–0.09→**0.08–0.15** | 2–3→**3–5** | 2.1→**5.8** |
| `venom-head` | 40→**50** | 0.04–0.08→**0.07–0.13** | 2–2.5→**3–4.5** | 1.4→**5.0** |

Head gradients also shifted to use tinted starts instead of pure white, matching their parent trail colors.

#### Fix 4: CC presets — now receive correct emission rates

No JSON changes needed — the Emitter.js bug fix is sufficient:
- **stun-stars:** now correctly emits 6/sec (was 30/sec from bug), ~4.2 alive particles (was 21.0)
- **slow-frost:** now correctly emits 5/sec (was 30/sec from bug), ~3.0 alive particles (was 18.0)

#### Files Changed
- `client/src/canvas/particles/Emitter.js` — Read `em.rate` as fallback for `em.spawnRate` (constructor + `applyPreset()`)
- `client/public/particle-presets.json` — Tuned 16 presets (10 trails + 6 heads): lifetimes, sizes, rates, gradients. Fixed soul-reap-trail green→purple gradient.

#### Design Decisions
- **Read both field names (`spawnRate || rate`)** rather than renaming all presets — backwards-compatible with existing presets that use `spawnRate`, and the Lab tool also uses `rate`. No breaking changes.
- **~9–12 alive trail particles** as the target range — enough for a visible ribbon behind the projectile without excessive GPU/CPU cost. 16 presets × ~10 particles = ~160 particles peak during a busy combat frame, well within the 500-per-emitter cap.
- **~5–6 alive head particles** — creates a bright, clearly visible "tip" that reads as the projectile itself, while the trail reads as its path. Head particles are intentionally larger and brighter than trail particles.
- **Tinted whites instead of pure white** — shifts color perception earlier. A warm yellow-white (`#ffffcc`) immediately reads as "holy/fire", while a cool blue-white (`#eeffff`) reads as "ice". The color gradient doesn't need to reach its mid-stop for the player to associate it with a skill family.
- **No changes to projectile speeds or arcs** — only the visual trail/head density was the issue, not the flight dynamics.

### 14G Addendum 2 — Projectile Speed & Arc Tuning Pass (February 28, 2026)

**Status:** COMPLETE

#### Problem: All projectiles feel like "lobbing a rock"

After the visibility bug fix, projectile trails were visible but every spell and ability felt slow and floaty. Root causes:

1. **All speeds in a narrow 300–450 px/s band** — a basic auto-attack arrow (350) and a devastating Soul Reap (350) traveled at nearly identical speed. No spell felt impactful or distinct.
2. **Magic spells had physical arcs** — Wither (arc 0.08), Rebuke (arc 0.05), and Power Shot (arc 0.2) all lobbed upward. Magic should fly flat/straight; only arrows should arc. Power Shot had the *highest* arc, making the Ranger's strongest skill look the most like a lobbed rock.
3. **Travel times too long at typical ranges** — At 5 tiles (240px), most projectiles took 0.5–0.8 seconds to arrive. In a 1-second turn tick game, half the turn is spent watching a slow projectile drift across the screen.

#### Speed/Arc Math Reference

TILE_SIZE = 48px. Typical engagement: 3–6 tiles = 144–288px. Diagonal 7 tiles = ~339px.

**Before (old values — 300–450 px/s, everything feels the same):**

| Skill | Speed | Arc | 5-tile arrival | Feel |
|-------|-------|-----|----------------|------|
| Wither | 300 | 0.08 | 0.80s | Slow curse lob |
| Venom Gaze | 300 | 0 | 0.80s | Slow eye beam |
| ranged_attack | 350 | 0.15 | 0.69s | Lobbed rock |
| Crippling Shot | 350 | 0.15 | 0.69s | Lobbed rock |
| Soul Reap | 350 | 0 | 0.69s | Slow dark bolt |
| Power Shot | 400 | **0.2** | 0.60s | Biggest lob |
| Exorcism | 400 | 0 | 0.60s | Floaty bolt |
| Rebuke | 450 | 0.05 | 0.53s | Still leisurely |

**After (new values — three distinct speed tiers with intentional arc design):**

| Skill | Speed | Arc | 5-tile arrival | Feel | Tier |
|-------|-------|-----|----------------|------|------|
| **Soul Reap** | **1000** | **0** | **0.12s** | Near-instant dark devastation | Fast Magic |
| **Rebuke** | **950** | **0** | **0.13s** | Snappy divine bolt | Fast Magic |
| **Exorcism** | **850** | **0** | **0.14s** | Fast holy beam | Fast Magic |
| **Power Shot** | **700** | **0.12** | **0.17s** | Fast powerful arrow, subtle arc | Fast Arrow |
| **Venom Gaze** | **650** | **0** | **0.18s** | Quick poison eye beam | Medium Magic |
| **Wither** | **600** | **0** | **0.20s** | Purposeful dark curse bolt | Medium Magic |
| **ranged_attack** | **520** | **0.10** | **0.23s** | Standard arrow, gentle arc | Standard Arrow |
| **Crippling Shot** | **520** | **0.08** | **0.23s** | Standard arrow, slight arc | Standard Arrow |

#### Design: Three Speed Tiers

| Tier | Category | Speed Range | Arc | 5-tile Arrival | Fantasy |
|------|----------|-------------|-----|----------------|---------|
| **Fast Magic** | Rebuke, Exorcism, Soul Reap | 850–1000 | 0 | 0.12–0.14s | Snap-to-target devastating spells |
| **Medium Magic** | Wither, Venom Gaze | 600–650 | 0 | 0.18–0.20s | Deliberate but purposeful curses |
| **Physical Arrows** | Auto, Power Shot, Crippling | 520–700 | 0.08–0.12 | 0.17–0.23s | Fast arrows with gentle realistic arcs |

Key decisions:
- **Soul Reap is the fastest** (1000 px/s) — it's a devastating nuke that should feel like getting hit by lightning
- **Rebuke close behind** (950) — divine wrath snaps to target
- **Power Shot fastest arrow** (700) with reduced arc (0.12 vs old 0.2) — a *power* shot, not a mortar
- **All magic arcs removed** — magic flies in straight lines. Period. Arcs are reserved for physical projectiles
- **Arrow arcs reduced globally** — 0.08–0.12 range gives gentle realistic parabolas without the "lobbing" feel

#### Trail Emission Rate Increases

Faster projectiles need denser particle emission to maintain visible trails during shorter flight times. All 10 trail presets and 4 head presets were tuned:

**Trail presets:**

| Preset | Old Rate | New Rate | Used By | Rationale |
|--------|----------|----------|---------|-----------|
| `soul-reap-trail` | 45 | **80** | Soul Reap (1000 px/s) | Fastest spell needs densest trail |
| `rebuke-trail` | 50 | **80** | Rebuke (950 px/s) | Near-instant, needs thick ribbon |
| `exorcism-trail` | 55 | **75** | Exorcism (850 px/s) | Fast holy beam |
| `power-shot-trail` | 50 | **70** | Power Shot (700 px/s) | Fast arrow |
| `holy-bolt-trail` | 45 | **60** | (generic holy) | Medium bump |
| `dark-bolt-trail` | 40 | **60** | (generic dark) | Medium bump |
| `venom-trail` | 40 | **60** | Venom Gaze (650 px/s) | Medium magic |
| `wither-trail` | 35 | **55** | Wither (600 px/s) | Deliberate curse |
| `arrow-trail` | 40 | **55** | Auto ranged (520 px/s) | Standard arrow |
| `crip-shot-trail` | 45 | **55** | Crippling Shot (520 px/s) | Standard arrow |

**Head presets:**

| Preset | Old Rate | New Rate | Rationale |
|--------|----------|----------|-----------|
| `holy-head` | 60 | **80** | Powers Rebuke (950) & Exorcism (850) |
| `dark-head` | 50 | **70** | Powers Soul Reap (1000) & Wither (600) |
| `power-shot-head` | 60 | **70** | Powers Power Shot (700) |
| `venom-head` | 50 | **65** | Powers Venom Gaze (650) |
| `arrow-head` | 55 | 55 | Unchanged — 520 px/s is fine at current rate |
| `ice-arrow-head` | 55 | 55 | Unchanged — same speed tier |

#### Files Changed
- `client/public/particle-effects.json` — Updated speed and arc values for all 8 projectile mappings
- `client/public/particle-presets.json` — Increased emission rates for 10 trail presets and 4 head presets

#### Impact Summary
- **Zero code changes** — pure JSON config tuning
- **No new presets** — only parameter adjustments to existing presets
- **Average arrival time reduced from ~0.65s → ~0.17s** — spells feel snappy and impactful
- **Speed differentiation range expanded from 1.5× (300–450) → 1.9× (520–1000)** — each spell has distinct flight personality
- **Magic arcs eliminated** — only physical arrows arc, matching genre expectations

---

## Priority 14H — Persistent Status Effect Overlays

*Units with active buffs/debuffs should show subtle looping visual indicators for the duration.*

### Current Behavior
- Particle effects fire once on cast, then disappear
- A Withered enemy looks identical to a non-Withered enemy after the initial 0.5s effect
- A Warded unit has a buff icon but no persistent visual on the sprite

### Implementation

**Approach:** When certain buffs appear in a unit's `active_buffs`, the `ParticleManager` maintains a looping emitter at that unit's position until the buff expires.

**In `client/src/canvas/particles/ParticleManager.js`:**

New method `updateStatusEffects(players)` called each frame (or on state change):

1. Scan all visible players for specific buff types in `active_buffs`
2. If a buff is present and no looping emitter exists for that unit+buff, create one
3. If a buff expired (emitter exists but buff is gone), stop the emitter
4. Use tracked emitters (already supported via `follow: true`) to follow units

### Status Effect → Visual Map

| Buff Type | Preset (reuse or new) | Visual | Intensity |
|-----------|----------------------|--------|-----------|
| `dot` (Wither) | New: `status-wither-loop` | Faint purple wisps rising from unit | Very subtle |
| `dot` (Venom Gaze) | New: `status-poison-loop` | Faint green bubbles around feet | Very subtle |
| `hot` (Prayer) | New: `status-prayer-loop` | Soft golden motes drifting upward | Very subtle |
| `shield_charges` (Ward) | Reuse: `ward-barrier` (loop) | Faint crystalline shimmer | Very subtle |
| `buff` armor (Bulwark/SoF) | New: `status-armor-loop` | Faint stone/silver particles at feet | Very subtle |
| `buff` melee (War Cry) | New: `status-warcry-loop` | Faint red embers around hands | Very subtle |
| `evasion` | New: `status-evasion-loop` | Occasional wisp/blur flash | Very subtle |

**Key design constraint:** These must be VERY subtle — low particle count (3–5 per burst), low alpha (0.2–0.4), small size — so they don't create visual noise when 8+ units all have active buffs. They're ambient indicators, not flashy effects.

### New Presets Needed
- 6–7 new `status-*-loop` presets with `loop: true`, low burst count, long duration

### Files Changed
- `client/src/canvas/particles/ParticleManager.js` — New `updateStatusEffects()` method
- `client/public/particle-presets.json` — Add ~7 subtle looping presets
- `client/src/components/Arena/Arena.jsx` — Call `updateStatusEffects()` on player state change

### Testing
- Manual: cast Wither → verify subtle purple wisps persist for 4 turns, then stop
- Manual: cast Ward → verify shimmer persists until charges depleted
- Performance: verify 8 units with 2 buffs each doesn't impact frame rate
- Verify status emitters clean up on unit death

---

## Priority 14I — AoE Ground Indicators on Resolution

*When AoE skills resolve, briefly highlight the affected tile radius on the ground.*

### Current Behavior
- Volley and Holy Ground affect tiles within a radius, but the player only sees individual damage/heal floaters
- There's no visual showing the *area* that was affected

### Implementation

**In `client/src/canvas/overlayRenderer.js`:**

New function `drawAoEIndicator(ctx, centerX, centerY, radius, color, age, ox, oy)`:

1. Draw a translucent filled circle/diamond centered on the target tile
2. Fade out over ~1 second (similar to damage floaters)
3. Color matches the skill theme (gold for Holy Ground, brown/red for Volley)

**In `client/src/context/reducers/combatReducer.js`:**

Add an `aoeIndicators` array to state. When AoE skill results arrive, push an indicator:

```javascript
{ x, y, radius, color, createdAt: Date.now() }
```

### AoE Skills

| Skill | Radius | Color | Shape |
|-------|--------|-------|-------|
| `holy_ground` | 1 tile | `rgba(255, 215, 0, 0.2)` gold | Circle |
| `volley` | 2 tiles | `rgba(200, 100, 50, 0.2)` brown | Circle |
| `taunt` | 2 tiles | `rgba(255, 60, 60, 0.15)` red | Circle |

### Files Changed
- `client/src/canvas/overlayRenderer.js` — New `drawAoEIndicator()` function
- `client/src/context/reducers/combatReducer.js` — Track `aoeIndicators` in state
- `client/src/canvas/ArenaRenderer.js` — Render AoE indicators in frame loop

### Testing
- Manual: Crusader uses Holy Ground → golden circle appears around them for ~1s
- Manual: Ranger uses Volley → brown circle appears at target location for ~1s

---

## Implementation Order & Dependencies

```
14A  New presets (standalone)
 │
 ├─► 14B  Wire mappings (depends on 14A)
 │    │
 │    ├─► 14G  Projectile travel (extends 14B mappings)
 │    │
 │    └─► 14H  Status overlays (extends 14A presets + 14B mappings)
 │
 ├─► 14C  DoT/HoT floaters (standalone)
 │
 ├─► 14D  Miss/Dodge floaters (standalone, can reuse 14A evasion-blur)
 │
 ├─► 14E  Stun/Slow overlays (standalone)
 │
 ├─► 14F  Critical hit emphasis (standalone, uses existing preset)
 │
 └─► 14I  AoE indicators (standalone)
```

### Suggested Session Plan

| Session | Tasks | Estimated Effort |
|---------|-------|-----------------|
| **Session 1** | 14A (author 9 presets) + 14B (wire mappings) | 1–2 hours |
| **Session 2** | 14C (tick floaters) + 14D (miss/dodge floaters) + 14F (critical emphasis) | 1–2 hours |
| **Session 3** | 14E (CC overlays) + 14I (AoE indicators) | 1–2 hours |
| **Session 4** | 14G (projectile travel system) | 2–3 hours |
| **Session 5** | 14H (persistent status overlays) | 2–3 hours |

### Test Count Target
- Existing: 1,641+ tests, 0 failures
- Expected additions: ~20–30 new tests (floater generation, CC indicator logic, AoE indicator lifecycle)
- Target: **1,670+ tests**, 0 failures

---

## Files Summary

| File | Changes |
|------|---------|
| `client/public/particle-presets.json` | +9 skill presets (14A), +3 trail presets (14G), +7 status-loop presets (14H) |
| `client/public/particle-effects.json` | +9 skill mappings (14B), +1 combat mapping (14D), projectile configs (14G) |
| `client/src/context/reducers/combatReducer.js` | Tick floaters (14C), miss/dodge floaters (14D), AoE indicators (14I) |
| `client/src/canvas/overlayRenderer.js` | Scaled floater font (14F), AoE indicator renderer (14I) |
| `client/src/canvas/unitRenderer.js` | CC visual indicators (14E) |
| `client/src/canvas/ArenaRenderer.js` | Wire CC indicators (14E), AoE indicators (14I) |
| `client/src/canvas/particles/ParticleManager.js` | Critical-hit trigger (14F), dodge detection (14D), status effects (14H), projectile support (14G) |
| `client/src/canvas/particles/ParticleProjectile.js` | **New file** — projectile travel system (14G) |
| `client/src/components/Arena/Arena.jsx` | Status effect updates (14H) |

---

## Non-Goals (Out of Scope)

- **Screen shake** — could enhance big hits but adds complexity and accessibility concerns
- **Sound effects** — audio exists in `Assets/Audio/` but wiring it is a separate phase
- **Skill animation frames** — sprite-based cast animations would require new art assets
- **Combo indicators** — visual chains for skill combos (e.g., "Wither → Soul Reap") — future phase
- **Minimap effect indicators** — showing particle effects on the minimap — not worth the clutter
