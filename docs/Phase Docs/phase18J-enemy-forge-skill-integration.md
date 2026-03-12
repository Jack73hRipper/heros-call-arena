# Phase 18J — Enemy Forge Skill Integration

**Created:** March 3, 2026
**Status:** J1 Complete, J2 Complete, J3 Complete, J4 Complete, J5 Complete
**Previous:** Phase 18I (Enemy Identity Skills)
**Goal:** Update the Enemy Forge tool to fully represent, edit, and simulate the 5 new enemy identity skills from Phase 18I, plus improve class_id UX and Super Unique encounter previews.

---

## Background

Phase 18I added 5 new skills (Enrage, Bone Shield, Frenzy Aura, Dark Pact, Profane Ward) and 3 new effect types (`passive_enrage`, `damage_absorb`, `passive_aura_ally_buff`) to the combat system. The Enemy Forge tool (18H) was built before these skills existed and currently:

- Has `class_id` as a **free-text input** (easy to typo, no discovery of valid options)
- Shows skills as **read-only name chips** with no effect detail breakdown
- Runs a **pure auto-attack TTK simulator** that ignores all skill effects entirely
- Shows **no skill info** in the Super Unique encounter preview or browser list
- Has no awareness of the new effect types or their balance-relevant parameters

This means the Forge can't currently be used to balance the very skills it was designed to support.

---

## Table of Contents

1. [Phase J1 — Class ID Dropdown & Skill Discovery](#1-phase-j1--class-id-dropdown--skill-discovery)
2. [Phase J2 — Skill Detail Panel](#2-phase-j2--skill-detail-panel)
3. [Phase J3 — Browser Skill Badges](#3-phase-j3--browser-skill-badges)
4. [Phase J4 — Simulator Skill Integration](#4-phase-j4--simulator-skill-integration)
5. [Phase J5 — Super Unique Encounter Skill Preview](#5-phase-j5--super-unique-encounter-skill-preview)

---

## 1. Phase J1 — Class ID Dropdown & Skill Discovery

**Goal:** Replace the free-text `class_id` input with a dropdown populated from `skills_config.class_skills` keys, so developers can see all valid class assignments at a glance.
**File:** `tools/enemy-forge/src/components/EnemyEditor.jsx`
**Complexity:** Low

### What Changes

- The `class_id` field in the Enemy Editor's "Class & Skills" card is currently:
  ```jsx
  <input type="text" value={enemy.class_id || ''} onChange={...} placeholder="(none — no skills)" />
  ```
- Replace with a `<select>` dropdown populated from `Object.keys(skills.class_skills || {})`.
- Include a blank `"(none)"` option that clears the `class_id`.
- Show the skill count next to each option for quick reference: e.g. `"skeleton (2 skills)"`, `"demon_enrage (1 skill)"`.
- Sort options alphabetically, with hero classes (crusader, confessor, etc.) grouped at the bottom or visually separated since they're not typically assigned to enemies.

### Why This Matters

With 26+ `class_skills` entries now in the config (including `demon_enrage`, `imp_frenzy`, `dark_priest`, `acolyte`, `skeleton`, etc.), a free-text field is error-prone. Developers need to **see** valid options and pick from them — especially when assigning the new 18I class IDs.

### Checklist

| # | Task | Status |
|---|---|---|
| J1.1 | Replace `class_id` text input with `<select>` dropdown | ✅ Done |
| J1.2 | Populate options from `skills.class_skills` keys | ✅ Done |
| J1.3 | Add "(none)" option that sets `class_id` to `undefined` | ✅ Done |
| J1.4 | Show skill count per class option | ✅ Done |

**Implementation Notes (J1):**
- Replaced `<input type="text">` with `<select>` dropdown using `<optgroup>` for visual separation
- Enemy classes (20 options: `acolyte`, `construct`, `dark_priest`, `demon_enrage`, etc.) sorted alphabetically in "Enemy Classes" group
- Hero classes (`confessor`, `crusader`, `hexblade`, `inquisitor`, `mage`, `ranger`) in separate "Hero Classes" group at bottom
- Each option shows skill count: e.g. `skeleton (2 skills)`, `demon_enrage (1 skill)`
- Blank `""` option clears `class_id` to `undefined` (no skills)
- No new dependencies; uses existing `skills` prop already passed to `EnemyEditor`

---

## 2. Phase J2 — Skill Detail Panel

**Goal:** Expand the read-only skill chips in the Enemy Editor into a detailed breakdown showing each skill's effects, values, cooldowns, and targeting — making it possible to understand and balance enemy abilities without leaving the Forge.
**File:** `tools/enemy-forge/src/components/EnemyEditor.jsx`
**Complexity:** Medium

### What Changes

Currently, skills are displayed as minimal chips:
```
[🔥 Enrage] [CD:0 R:0]
```

This tells you nothing about the 30% HP threshold, the 1.5× damage multiplier, or the fact that it's a passive. Replace with an expandable detail panel:

#### Skill Card Layout (per skill)

```
┌─────────────────────────────────────────────┐
│ 🔥 Enrage                        [passive]  │
│ "When HP drops below 30%, permanently gain   │
│  +50% melee damage."                         │
│                                              │
│  Targeting: passive    Range: 0    CD: 0     │
│                                              │
│  Effects:                                    │
│  ┌─ passive_enrage ────────────────────────┐ │
│  │  HP Threshold: 30%                      │ │
│  │  Damage Multiplier: 1.5×               │ │
│  └─────────────────────────────────────────┘ │
└─────────────────────────────────────────────┘
```

#### Effect Type Renderers

Each effect type gets a human-readable renderer:

| Effect Type | Display |
|---|---|
| `passive_enrage` | HP Threshold: **30%**, Damage Multiplier: **1.5×** |
| `damage_absorb` | Absorb Amount: **25**, Duration: **4 turns** |
| `passive_aura_ally_buff` | Stat: **attack_damage +3**, Radius: **2 tiles**, Requires Tag: **imp** |
| `buff` (melee_damage_multiplier) | Stat: **melee_damage_multiplier**, Magnitude: **1.25×**, Duration: **3 turns** |
| `buff` (damage_reduction_pct) | Stat: **damage_reduction_pct**, Magnitude: **30%**, Duration: **3 turns** |
| `stat_multiplier` | Stat: **{stat}**, Value: **{value}×** |
| `set_stat` | Stat: **{stat}**, Value: **{value}** |
| `heal` | Amount: **{amount}** |
| `damage` | Amount: **{amount}**, Type: **{damage_type}** |

#### Passive Badge

Skills with `is_passive: true` get a colored `[PASSIVE]` badge to distinguish them from active skills. This is critical for understanding that Enrage and Frenzy Aura don't require AI action — they trigger automatically.

### Checklist

| # | Task | Status |
|---|---|---|
| J2.1 | Create `SkillDetailCard` sub-component with description, targeting, range, cooldown | ✅ Done |
| J2.2 | Add effect type renderer function mapping effect types → readable labels | ✅ Done |
| J2.3 | Render all effects inside each skill card with their parameters | ✅ Done |
| J2.4 | Add `[PASSIVE]` badge for `is_passive: true` skills | ✅ Done |
| J2.5 | Add CSS for the skill detail cards (grimdark theme consistent) | ✅ Done |

**Implementation Notes (J2):**
- Created new `SkillDetailCard.jsx` component (`tools/enemy-forge/src/components/SkillDetailCard.jsx`)
- Implemented `EFFECT_RENDERERS` map covering **17 effect types**: `passive_enrage`, `damage_absorb`, `passive_aura_ally_buff`, `buff`, `stat_multiplier`, `set_stat`, `heal`, `hot`, `damage`, `melee_damage`, `ranged_damage`, `magic_damage`, `holy_damage`, `teleport`, `dot`, `shield_charges`, `detection`, `taunt`, `stun_damage`, `aoe_heal`, `aoe_damage`, `aoe_damage_slow`, `evasion`, `ranged_damage_slow` (25 total renderers)
- Unknown effect types fall through to a generic key-value dump renderer
- Each card displays: icon, name, `[PASSIVE]` badge (blue, for `is_passive: true`), `[AUTO]` badge (gray, for auto-attacks), italic description, targeting/range/cooldown meta bar, and collapsible effect blocks with labeled parameters
- Smart formatting: multiplier stats show `×` suffix, percentage stats show `%`, aura buffs show `+N` with stat name, DoTs/HoTs show per-tick and total values
- `TARGETING_LABELS` map provides emoji-prefixed labels for all 8 targeting types
- Passive skill cards get a blue left-border accent via `.skill-passive` CSS class
- Replaced the old `skill-list` → `skill-chip` rendering in `EnemyEditor.jsx` with `skill-detail-list` → `SkillDetailCard` per skill
- Added `~150 lines` of grimdark-themed CSS in `main.css` (dark input backgrounds, dim labels, bright values, accent-colored effect type headers, rounded borders)
- No new dependencies; component imports only React
- Build verified: `vite build` passes cleanly (43 modules, 0 errors)

---

## 3. Phase J3 — Browser Skill Badges

**Goal:** Show at a glance in the Enemy Browser sidebar which enemies have skills, how many, and whether they include passives.
**File:** `tools/enemy-forge/src/components/EnemyBrowser.jsx`
**Complexity:** Low

### What Changes

Add a small skill indicator badge to each enemy row in the browser list, next to the existing tag badges:

```
[Demon]        🔥 Enrage           [demon] [1 skill]
[Skeleton]     🦴 Bone Shield      [undead] [2 skills]
[Imp]          👹 Frenzy Aura      [demon] [1 skill] [passive]
[Dark Priest]  🩸 Dark Pact        [undead] [2 skills]
[Acolyte]      🛡️ Profane Ward     [undead] [2 skills]
[Zombie]       (no skills)         [undead]
```

- Enemies with skills: show a small `⚔ N` badge (e.g. `⚔ 2`)
- Enemies with passive-only skills: add a subtle `[P]` indicator
- Enemies with no `class_id` or no skills: no badge (silent absence)

#### Additionally: "Has Skills" filter

Add a third filter dropdown to the browser filters:
- **All** — show everything
- **Has Skills** — only enemies with `class_id` that maps to at least 1 skill
- **No Skills** — enemies without skills (useful for finding remaining skill-less enemies)

This requires passing `skills` config data into the `EnemyBrowser` component.

### Checklist

| # | Task | Status |
|---|---|---|
| J3.1 | Pass `skills` config to `EnemyBrowser` from `App.jsx` | ✅ Done |
| J3.2 | Resolve `class_id → class_skills → skill count` per enemy in browser | ✅ Done |
| J3.3 | Render skill count badge on each enemy row | ✅ Done |
| J3.4 | Add "Has Skills / No Skills" filter dropdown | ✅ Done |

**Implementation Notes (J3):**
- Added `skills={configs.skills}` prop to `<EnemyBrowser>` in `App.jsx`
- Created three helper functions in `EnemyBrowser.jsx`: `getSkillsForClassId(classId)`, `getSkillCount(classId)`, `hasPassiveSkill(classId)` — resolves `class_id → class_skills → skill IDs → skill data`
- Enemies with skills now show a blue `⚔ N` badge (e.g. `⚔ 2`) with tooltip showing skill count and class_id
- Enemies with passive skills additionally show a purple `P` badge with tooltip "Has passive skill(s)"
- Enemies with no `class_id` or 0 skills show no badge (silent absence, per spec)
- Added third filter dropdown to browser filters: "All Skills" / "Has Skills" / "No Skills" — filters using the resolved skill count
- `skillFilter` state added alongside existing `tagFilter` and `roleFilter`; included in `useMemo` dependency array for proper reactivity
- Added ~30 lines of CSS: `.tag-badge` base style (font, padding, border-radius), `.skill-badge` (blue accent with semi-transparent background), `.passive-badge` (purple accent, smaller font), `.enemy-tags` updated with `flex-wrap: wrap` to handle extra badges gracefully
- No new dependencies; uses existing `skills` config structure (`skills.class_skills` + `skills.skills`)
- Build verified: `vite build` passes cleanly (43 modules, 0 errors)

---

## 4. Phase J4 — Simulator Skill Integration

**Goal:** Upgrade the TTK Simulator to model the 5 new enemy skill effects so balance numbers are accurate for skilled enemies.
**File:** `tools/enemy-forge/src/components/Simulator.jsx`
**Complexity:** High (most impactful change)

### Current Problem

The simulator runs a pure auto-attack loop:
```
Each turn:
  1. Each living hero deals (hero.damage - enemy.armor) to enemy
  2. Enemy deals (enemy.damage - hero.armor) to random living hero
```

This completely ignores:
- **Enrage** — Demon's damage should spike 1.5× once below 30% HP, making the last phase of the fight much more dangerous
- **Bone Shield** — Skeleton absorbs 25 damage every 6 turns, effectively adding significant EHP
- **Frenzy Aura** — Multiple imps stack +3 damage each, but the simulator only tests 1 enemy at a time
- **Dark Pact** — Dark Priest buffs an ally's damage by +25% for 3 turns
- **Profane Ward** — Acolyte reduces an ally's damage taken by 30% for 3 turns

### Simulation Model Upgrades

#### 4A — Enrage Integration

In the turn loop, after the enemy takes damage:
```javascript
// Check enrage trigger
if (hasEnrage && !enrageTriggered && enemyHp / enemyMaxHp <= enrageThreshold) {
  enrageTriggered = true;
  enemyMeleeDamage = Math.round(enemyMeleeDamage * enrageDamageMultiplier);
}
```

**Balance impact:** Demons become significantly more dangerous in the last third of the fight. TTK may not change much, but danger score should increase.

#### 4B — Bone Shield Integration

Track an absorb shield with cooldown:
```javascript
// Enemy turn: try to cast bone shield if off cooldown
if (hasBoneShield && boneShieldCooldown <= 0 && boneShieldAbsorb <= 0) {
  boneShieldAbsorb = 25;
  boneShieldDuration = 4;
  boneShieldCooldown = 6;
}

// When enemy takes damage:
if (boneShieldAbsorb > 0) {
  const absorbed = Math.min(dmg, boneShieldAbsorb);
  boneShieldAbsorb -= absorbed;
  dmg -= absorbed;
}
```

**Balance impact:** Skeletons gain effective HP. With a 6-turn CD and 25 absorb, they're meaningfully tankier.

#### 4C — Frenzy Aura (Group Simulation Mode)

This requires a new simulation input: **enemy count**. When testing imps, you should be able to say "4 imps together" and the simulator models:
- Each imp gets `+3 × (nearbyImps - 1)` bonus damage from Frenzy Aura
- All imps attack the party (total incoming damage = impCount × impDamage)

Add an **"Enemy Count"** input to the simulator (default 1). When > 1:
- If the enemy has `frenzy_aura` skill, calculate stacked aura bonus
- Divide hero attacks across multiple enemies or focus-fire the first

**Balance impact:** A single imp deals 8 damage. 4 clustered imps with Frenzy Aura: 8 + (3 × 3) = 17 damage each, 68 total — massive difference.

#### 4D — Dark Pact / Profane Ward (Support Pair Simulation)

Add a **"Support Enemy"** dropdown to the simulator. When set, the simulation includes a secondary enemy unit that:
- **Dark Pact:** Every 5 turns, buffs the primary enemy's damage by 1.25× for 3 turns
- **Profane Ward:** Every 6 turns, reduces damage taken by the primary enemy by 30% for 3 turns

The support enemy also attacks the party with its own stats (but is a lower priority target).

**Balance impact:** A Dark Priest buffing a Werewolf turns it from 15 → 18.75 damage. An Acolyte warding a Bruiser makes it 30% harder to kill periodically.

#### 4E — Skill Details in Results

Add a new section to the simulation results output:

```
Skill Effects Impact:
  🔥 Enrage triggered at turn 4.2 avg (30% HP threshold)
     → Post-enrage DPS: 22 → 33/turn
  🦴 Bone Shield active 4.1 turns per fight avg
     → Damage absorbed: 38 avg
  👹 Frenzy Aura: +9 damage per imp (3 nearby)
  🩸 Dark Pact uptime: 60% of fight
     → Avg buffed damage: +18%
  🛡️ Profane Ward uptime: 50% of fight  
     → Avg damage reduction: -15%
```

### Checklist

| # | Task | Status |
|---|---|---|
| J4.1 | Add skill detection helper: resolve enemy's `class_id` → skills → effect types | ✅ Done |
| J4.2 | Implement Enrage trigger in simulation loop (HP threshold → permanent damage bonus) | ✅ Done |
| J4.3 | Implement Bone Shield in simulation loop (absorb shield with cooldown tracking) | ✅ Done |
| J4.4 | Add "Enemy Count" input for group simulation (Frenzy Aura stacking) | ✅ Done |
| J4.5 | Add "Support Enemy" dropdown for Dark Pact / Profane Ward pair simulation | ✅ Done |
| J4.6 | Implement Dark Pact buff logic in simulation (periodic damage multiplier on primary) | ✅ Done |
| J4.7 | Implement Profane Ward buff logic in simulation (periodic damage reduction on primary) | ✅ Done |
| J4.8 | Add "Skill Effects Impact" section to simulation results | ✅ Done |
| J4.9 | Update batch simulation to account for skills (flag skill-enhanced enemies in results) | ✅ Done |

**Implementation Notes (J4):**
- Created `resolveEnemySkills(enemy, skillsConfig)` helper function that resolves `class_id → class_skills → skill data` and extracts typed effects (`enrage`, `boneShield`, `frenzyAura`, `darkPact`, `profaneWard`) into a structured `effects` object
- Rewrote `simulateEncounter()` from a 60-line pure auto-attack loop into a ~180-line skill-aware simulation engine accepting `options = { enemyCount, supportEnemy, skillsConfig }`
- **Enrage (J4.2):** After heroes deal damage, checks if enemy HP ≤ threshold (30%) — permanently multiplies melee by `damage_multiplier` (1.5×). Tracks trigger turn and rate per trial
- **Bone Shield (J4.3):** Each enemy unit independently tracks `shieldAbs`, `shieldDur`, `shieldCD`. Casts on self when off cooldown and no active shield. Absorbs incoming hero damage before HP reduction. Duration ticks and expires shield when done
- **Frenzy Aura (J4.4):** New "Enemy Count" range input (1–8). When count > 1 and enemy has `passive_aura_ally_buff`, applies `+value × (count-1)` bonus damage to each unit. All units attack independently, heroes focus-fire first alive
- **Support Enemy (J4.5):** New "Support Enemy" dropdown populated from `supportCandidates` memo — auto-discovers all enemies with Dark Pact or Profane Ward skills. Shows their stats in a stat-callout preview
- **Dark Pact (J4.6):** Support enemy casts buff on cooldown, buffing primary enemies' melee damage by `magnitude×` for `duration_turns`. Uptime, bonus damage, and percentage tracked per trial
- **Profane Ward (J4.7):** Support enemy casts ward on cooldown, reducing hero damage to primary enemies by `magnitude%` for `duration_turns`. Uptime and damage reduced tracked per trial
- **Skill Impact Results (J4.8):** New `sim-skill-impact` section renders after DPS Breakdown when skills are active. Shows per-skill rows with icon, name, computed metrics: trigger turn/rate (Enrage), active turns/absorbed (Bone Shield), per-unit bonus/group DPS (Frenzy Aura), uptime %/bonus damage (Dark Pact), uptime %/damage reduced (Profane Ward)
- **Batch Simulation (J4.9):** Pass `skillsConfig` to batch encounters so skills affect results. Added "Skills" column to batch table showing resolved skill icons+names per enemy, or "—" for skillless enemies
- Added `enemySkillInfo` memo showing skill chips on selected enemy in the controls panel
- Added `~65 lines` of CSS in `main.css`: `.sim-skill-summary` (chip row), `.sim-skill-chip` (blue accent), `.sim-aura-preview` (orange accent for frenzy preview), `.sim-skill-impact` (bordered section), `.skill-impact-row` (panel-bg card per skill), `.skill-impact-icon`, `.skill-impact-detail`, `.skill-impact-stat`
- No new dependencies; uses existing `skills` prop already passed to `Simulator`
- Build verified: `vite build` passes cleanly (43 modules, 0 errors)

---

## 5. Phase J5 — Super Unique Encounter Skill Preview

**Goal:** Show the complete tactical picture in the Super Unique Editor's encounter preview — including the boss's own skills and the skills of its retinue members.
**File:** `tools/enemy-forge/src/components/SuperUniqueEditor.jsx`
**Complexity:** Medium

### What Changes

The current Encounter Preview card shows:
```
Malgris the Defiler
  Pit Lord of the Lower Catacombs
  "The stench of brimstone precedes him..."
  HP: 420  Melee: 30  Ranged: 0  Armor: 10
  Affixes: Extra Strong, Fire Enchanted
  Retinue: 3× Imp, 1× Acolyte
  Floors: 3–5
```

Extend to also show:

```
  Boss Skills: (resolved from base_enemy → class_id → class_skills)
    🔥 Enrage (passive) — +50% melee below 30% HP

  Retinue Skills:
    Imp (×3): 👹 Frenzy Aura (passive) — +3 dmg per nearby imp
    Acolyte (×1): 🛡️ Profane Ward — 30% dmg reduction for 3 turns, 💚 Heal

  Encounter Summary:
    Total enemies: 5 (1 boss + 4 retinue)
    Total HP pool: 420 + 180 + 80 = 680
    Threat notes:
      ⚠ Imps gain +6 dmg each from Frenzy Aura (3 nearby)
      ⚠ Acolyte will ward lowest-HP ally, extending fight
      ⚠ Boss enrages at 126 HP — watch for damage spike
```

This requires passing `skills` config to the `SuperUniqueEditor` component (currently not passed).

### Checklist

| # | Task | Status |
|---|---|---|
| J5.1 | Pass `skills` config to `SuperUniqueEditor` from `App.jsx` | ✅ Done |
| J5.2 | Resolve boss skills from `base_enemy → enemies_config class_id → class_skills` | ✅ Done |
| J5.3 | Resolve retinue member skills for each retinue entry | ✅ Done |
| J5.4 | Render "Boss Skills" section in encounter preview | ✅ Done |
| J5.5 | Render "Retinue Skills" section with per-member skill list | ✅ Done |
| J5.6 | Add "Encounter Summary" with total HP pool and tactical threat notes | ✅ Done |

**Implementation Notes (J5):**
- Added `skills={configs.skills}` prop to `<SuperUniqueEditor>` in `App.jsx` (J5.1)
- Created `resolveSkillsForClass(classId, skillsConfig)` helper that resolves `class_id → class_skills → skill IDs → full skill objects` from skills config
- Created `skillOneLiner(skill)` helper that generates concise human-readable summaries for 12+ effect types: `passive_enrage`, `damage_absorb`, `passive_aura_ally_buff`, `buff` (melee multiplier and damage reduction), `heal`, `melee_damage`, `ranged_damage`, `dot`, `aoe_damage`, `taunt`, `evasion`, `teleport`, `shield_charges`
- Created `buildThreatNotes(su, enemies, skillsConfig)` function that analyzes boss and retinue skills for tactical threats: enrage HP thresholds (computed from boss HP), damage absorb shields, frenzy aura stacking bonuses (computed from retinue count), damage reduction wards, melee damage buffs, and healer priority warnings
- Extracted the "Encounter Preview" into a standalone `EncounterPreview` sub-component for cleaner separation — accepts `su`, `enemies`, `rarity`, `skills` props
- **Boss Skills section (J5.4):** Resolves base_enemy → class_id → class_skills, renders each skill as a row with icon, name, `[passive]` badge (blue accent for `is_passive: true`), and italic one-liner summary
- **Retinue Skills section (J5.5):** Groups retinue by enemy type, resolves each member's class_id → skills, renders grouped skill rows with gold-colored enemy labels (`Name (×count):`) and indented skill rows underneath
- **Encounter Summary (J5.6):** Shows total enemy count (1 boss + N retinue), total HP pool (boss HP + individual retinue HP × count = total), and tactical "Threat Notes" panel with orange accent border — auto-generated warnings for enrage thresholds, aura stacking, damage buffs, wards, and healers
- Boss skills with `is_passive` get a blue left-border accent via `.su-skill-passive` CSS class
- Preserved all original preview content (identity, stats, affixes, retinue list, floors) — new sections append below
- Used `useMemo` for boss skills, retinue groups, and threat notes to avoid recomputation on unrelated re-renders
- Added `~130 lines` of grimdark-themed CSS in `main.css`: `.su-skills-section`, `.su-skills-heading`, `.su-skill-row`, `.su-skill-passive`, `.su-skill-badge`, `.su-skill-summary`, `.su-retinue-skill-group`, `.su-retinue-label`, `.su-encounter-summary`, `.su-summary-stats`, `.su-threat-notes`, `.su-threat-heading`, `.su-threat-note`
- No new dependencies; uses existing `skills` config structure (`skills.class_skills` + `skills.skills`)
- Build verified: `vite build` passes cleanly (43 modules, 0 errors)

---

## Implementation Order

| Phase | Depends On | Est. Changes | Priority |
|---|---|---|---|
| **J1** — Class ID Dropdown | None | ~30 lines | **Do first** — quick win, unblocks discovery |
| **J2** — Skill Detail Panel | J1 (benefits from dropdown) | ~100 lines | Second — enables understanding |
| **J3** — Browser Skill Badges | None | ~40 lines | Can parallel with J2 |
| **J4** — Simulator Skills | J1 (needs skill resolution) | ~200 lines | Third — highest balance impact |
| **J5** — Super Unique Skills | J1 (needs skill resolution) | ~80 lines | Fourth — encounter context |

Total estimated: ~450 lines of new/modified JSX + CSS across 5 files.

---

## Files Modified

| File | Phase | Changes |
|---|---|---|
| `tools/enemy-forge/src/App.jsx` | J3, J5 | Pass `skills` config to `EnemyBrowser` and `SuperUniqueEditor` |
| `tools/enemy-forge/src/components/EnemyEditor.jsx` | J1, J2 | Class ID dropdown, skill detail panel with effect renderers |
| `tools/enemy-forge/src/components/EnemyBrowser.jsx` | J3 | Skill count badge, "Has Skills" filter, accepts `skills` prop |
| `tools/enemy-forge/src/components/Simulator.jsx` | J4 | Enrage, Bone Shield, Frenzy Aura, Dark Pact, Profane Ward simulation logic; enemy count input; support enemy dropdown; skill impact results |
| `tools/enemy-forge/src/components/SuperUniqueEditor.jsx` | J5 | Boss skills, retinue skills, encounter summary with threat notes |
| `tools/enemy-forge/src/styles/main.css` | J2 | Skill detail card styles |

---

## Exit Criteria

- Developers can assign `class_id` from a dropdown of all valid options (no typos)
- Each enemy's skills are displayed with full effect breakdowns (thresholds, absorb amounts, aura radii, buff magnitudes, durations)
- The browser shows which enemies have skills at a glance, with a filter for skill-less enemies
- TTK simulations account for Enrage damage spikes, Bone Shield absorb, Frenzy Aura stacking, Dark Pact/Profane Ward support buffs
- Super Unique encounters show the complete tactical picture including retinue skills and threat analysis
