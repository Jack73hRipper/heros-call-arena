# New Class Implementation Template

**Purpose:** Step-by-step protocol for an AI agent (or developer) to design and implement a new playable class for the Arena project. Based on the Phase 21 (Bard) implementation which was executed flawlessly — follow this structure exactly.

**Usage:** Copy this template into a new phase doc (e.g., `phase22-<classname>-class.md`), fill in every `{PLACEHOLDER}`, delete the instructional comments (`<!-- ... -->`), and execute phases A through G in order.

---

## Pre-Implementation Checklist

Before starting, gather this context:

- [ ] Read `README.md` for full project structure and architecture
- [ ] Read `server/configs/classes_config.json` for existing class definitions
- [ ] Read `server/configs/skills_config.json` for existing skills and effect types
- [ ] Read `server/app/core/skills.py` for the skill resolver and existing handlers
- [ ] Read `server/app/core/combat.py` for the damage pipeline
- [ ] Read `server/app/core/ai_skills.py` for AI role maps and skill logic
- [ ] Read `client/src/canvas/renderConstants.js` for class colors/shapes/names
- [ ] Read `client/src/canvas/unitRenderer.js` for shape rendering
- [ ] Read `docs/Game stats references/game-balance-reference.md` for balance context
- [ ] Run the full test suite (`pytest server/tests/`) to confirm green baseline before any changes

---

# Phase {N} — {ClassName} Class ({Role / Fantasy})

**Created:** {Month Year}
**Status:** Not Started
**Previous:** Phase {N-1} ({Previous Phase Name})
**Goal:** {One-paragraph summary of what this class adds to the game and why it's needed. State the gameplay gap it fills.}

---

## Overview

{2-3 sentences describing the class fantasy, tone, and gameplay identity. Keep it grimdark.}

**Role:** {Role label, e.g., "Offensive Support", "Ranged DPS", "Tank/Controller", etc.}

### Design Pillars

<!-- List 4-5 core design pillars. These are the NON-NEGOTIABLE principles that every decision must serve. -->

1. **{Pillar 1}** — {One sentence explaining why this matters}
2. **{Pillar 2}** — {One sentence}
3. **{Pillar 3}** — {One sentence}
4. **{Pillar 4}** — {One sentence}
5. **{Pillar 5 (optional)}** — {One sentence}

---

## Base Stats

<!-- 
GUIDELINES FOR STAT DESIGN:
- HP: Range 70-150. Squishy casters 70-80, supports 90-100, bruisers 110-120, tanks 140-150
- Melee Damage: 0-20. 0 = cannot melee, 6-10 = weak, 12-16 = moderate, 18-20 = strong
- Ranged Damage: 0-18. 0 = melee only, 8-10 = light, 12-14 = moderate, 16-18 = strong
- Armor: 1-8. 1 = cloth, 2-3 = light, 4-5 = medium, 6-8 = heavy
- Vision Range: 5-9. 5 = tanks, 6-7 = standard, 8-9 = scouts
- Ranged Range: 0-6. 0 = melee only, 3-4 = short, 5 = medium, 6 = long
- Allowed Weapons: Pick from [melee, ranged, caster, hybrid]
- Color: Must be visually distinct from ALL existing classes (check renderConstants.js)
- Shape: Must be unique. Existing: diamond (Crusader), cross (Confessor), triangle (Inquisitor), 
         square (Ranger), hexagon (Hexblade), star (Mage), crescent (Bard)

CURRENT CLASS STAT REFERENCE (update this before designing):
                  HP    Melee  Ranged  Armor  Vision  Range  Role
 Crusader ....   150      20       0      8       5      0   Tank
 Confessor ...   100       8       0      3       6      0   Defensive Support
 Inquisitor ..    80      10       8      4       9      5   Scout
 Ranger ......    80       8      18      2       7      6   Ranged DPS
 Hexblade ....   110      15      12      5       6      4   Hybrid DPS
 Mage ........    70       6      14      1       7      5   Caster DPS
 Bard ........    90      10      10      3       7      4   Offensive Support
 {NEW CLASS} .   ???     ???     ???    ???     ???    ???   {Role}
-->

| Stat | Value | Rationale |
|------|-------|-----------|
| **HP** | {value} | {Compare to existing classes, explain positioning} |
| **Melee Damage** | {value} | {Rationale} |
| **Ranged Damage** | {value} | {Rationale} |
| **Armor** | {value} | {Rationale} |
| **Vision Range** | {value} | {Rationale} |
| **Ranged Range** | {value} | {Rationale — 0 if melee-only} |
| **Allowed Weapons** | {categories} | {What weapon types fit the fantasy} |
| **Color** | `{#hex}` | {Color name — must be distinct from existing palette} |
| **Shape** | {shape_name} | {Unique shape — describe what it suggests} |

### Stat Comparison (All Classes)

<!-- Paste the full table with the new class included. This is critical for balance review. -->

```
                  HP    Melee  Ranged  Armor  Vision  Range  Role
 Crusader ....   150      20       0      8       5      0   Tank
 Confessor ...   100       8       0      3       6      0   Defensive Support
 Inquisitor ..    80      10       8      4       9      5   Scout
 Ranger ......    80       8      18      2       7      6   Ranged DPS
 Hexblade ....   110      15      12      5       6      4   Hybrid DPS
 Mage ........    70       6      14      1       7      5   Caster DPS
 Bard ........    90      10      10      3       7      4   Offensive Support
 {NEW} .......  {hp}    {mel}   {rng}  {arm}   {vis}  {rr}  {Role}
```

### Auto-Attack Damage (1.15× multiplier)

```
 {ClassName} .. {melee} × 1.15 = {result} melee per hit
               {ranged} × 1.15 = {result} ranged per hit (range {N})
```

{Brief note on where this falls in the damage hierarchy and whether that's intentional.}

---

## Skills

### Skill Overview

<!--
SKILL DESIGN RULES:
- Slot 0 is ALWAYS Auto Attack (melee or ranged depending on class range stat)
- Slots 1-4 are class skills
- Every class needs at least 1 signature skill that defines its identity
- Cooldowns: 4-8 turns typical. High-impact = 6-8, moderate = 4-6
- Range: Match the class's intended positioning (frontline=0-1, midline=3-4, backline=5-6)
- Check EXISTING effect types before creating new ones:
  EXISTING EFFECT TYPES (reuse when possible):
    - melee_damage        (Double Strike, etc.)
    - ranged_damage       (Power Shot, etc.)
    - magic_damage        (Fireball, etc.)
    - holy_damage         (Rebuke, Exorcism)
    - heal                (Heal — single target)
    - aoe_heal            (Consecrate — AoE heal)
    - buff                (War Cry — single/self buff)
    - debuff              (Wither — single target debuff)
    - aoe_damage          (Meteor — AoE damage)
    - aoe_damage_slow     (Frost Nova, Cacophony — AoE damage + slow)
    - aoe_buff            (Ballad of Might — AoE ally buff)
    - aoe_debuff          (Dirge of Weakness — AoE enemy debuff)
    - cooldown_reduction  (Verse of Haste — reduce ally cooldowns)
    - shield              (Confessor's Ward)
    - dot                 (Hexblade's Wither)
    - teleport            (Shadow Step)
    - taunt               (Crusader's Taunt)
  If you MUST create a new effect type, document it thoroughly in the "New Effect Types" section.
-->

| Slot | Skill | Effect Type | Target | Range | Cooldown | Summary |
|:----:|-------|------------|--------|:-----:|:--------:|---------|
| 0 | Auto Attack ({Melee/Ranged}) | {type} | entity | {range} | 0 | 1.15× {melee/ranged} damage |
| 1 | {Skill Name} | {type} (**NEW**/existing) | {target_type} | {range} | {cd} | {Brief effect} |
| 2 | {Skill Name} | {type} (**NEW**/existing) | {target_type} | {range} | {cd} | {Brief effect} |
| 3 | {Skill Name} | {type} (**NEW**/existing) | {target_type} | {range} | {cd} | {Brief effect} |
| 4 | {Skill Name} | {type} (**NEW**/existing) | {target_type} | {range} | {cd} | {Brief effect} |

### Skill Details

<!-- For EACH skill (slots 1-4), provide a detailed breakdown following this exact format: -->

#### {Skill Name} {Icon} ({Short Description})

```
Effect Type:   {type} (NEW or existing)
Targeting:     {self / entity / ground_aoe / ally_or_self / enemy}
Radius:        {N tiles, if AoE — omit if single target}
Range:         {N tiles, or "—" if self-cast}
Cooldown:      {N turns}
LOS Required:  {Yes/No}
Effect:        {Precise mechanical description}
```

**Design:** {Why this skill exists. What fantasy it serves. How it interacts with the kit.}

**Damage/healing/effect examples:**
```
{Show concrete numbers against typical targets. This prevents ambiguity during implementation.}
```

**Implementation:** {Which existing handler to clone/reuse. If new, describe the algorithm in 3-5 steps.}

**Balance lever:** {List the specific values that can be tuned post-launch, e.g., "Damage (15), cooldown (5), radius (2)"}

---

<!-- Repeat the above block for each skill -->

### Complete {ClassName} Kit

```
Slot 0: {Auto Attack description}
Slot 1: {Skill 1 one-line summary}
Slot 2: {Skill 2 one-line summary}
Slot 3: {Skill 3 one-line summary}
Slot 4: {Skill 4 one-line summary}
```

---

## DPS Contribution Analysis

<!-- 
This section is CRITICAL for balance sign-off. Show concrete numbers.
For DPS classes: show personal DPS vs existing classes.
For supports: show team DPS amplification.
For tanks: show survivability and threat generation.
For hybrids: show both.
-->

### Direct DPS (Personal)

```
{Show auto-attack DPS and skill DPS calculations}
```

### {Team Impact / Survivability / Control Analysis — adapt section title to role}

```
{Show concrete scenarios with real numbers, e.g.:
- "4-person party vs boss" for supports
- "1v1 vs Crusader" for DPS
- "Tanking 3 enemies" for tanks}
```

---

## AI Behavior ({ai_role} role)

<!--
EXISTING AI ROLES (check ai_skills.py for current list):
- melee_dps (Crusader, Inquisitor)
- ranged_dps (Ranger, Mage)
- support (Confessor)
- offensive_support (Bard)
- hybrid (Hexblade)

If needed, create a new role. Otherwise reuse an existing one.
-->

### AI Role: `{role_name}`

{2-3 sentences describing the AI strategy at a high level.}

### Decision Priority

```
1. {Highest priority skill} → {condition for use}
2. {Second priority skill} → {condition for use}
3. {Third priority skill} → {condition for use}
4. {Fourth priority skill} → {condition for use}
5. Auto-attack → fallback, target nearest enemy in range
```

### Positioning

- {Describe movement preference — frontline charge, midline support, backline kiting?}
- {Which existing movement helper to reuse, e.g., `_support_move_preference()`, aggressive charge, etc.}
- {Retreat conditions}

### Smart Targeting Logic (if applicable)

```python
# Pseudocode for any non-trivial target selection logic
# e.g., "Score each ally by X, pick highest" or "prioritize lowest-HP enemy"
```

---

## New Effect Types

<!-- 
Only fill this section if the class introduces NEW effect types not in the existing list above.
If ALL skills reuse existing types, write: "No new effect types. All skills reuse existing handlers."
-->

### Summary

| Effect Type | Complexity | Based On | Handler |
|-------------|-----------|----------|---------|
| `{new_type}` | {Low/Medium/High} | `{existing_handler}` pattern | `resolve_{new_type}()` |

### Effect Type Details

#### `{new_type}` — {Description} ({Skill Name})

```python
def resolve_{new_type}(player, action, skill_def, players, ...):
    """Docstring explaining what this does."""
    # Step 1: {Validate inputs / targeting}
    # Step 2: {Core logic}
    # Step 3: {Apply effects / buffs / damage}
    # Step 4: {Set cooldown}
    # Step 5: {Return ActionResult}
```

### Buff/Debuff System Integration

<!-- If any new buff/debuff stats are introduced, document EXACTLY where they need to be checked in the damage pipeline. -->

**New stat: `{stat_name}`**

Locations that must be updated:
1. `{file}` — `{function}` — {what to add}
2. `{file}` — `{function}` — {what to add}
{...}

<!-- If no new buff stats: "No new buff stats. All effects use existing buff system entries." -->

---

## Implementation Phases

<!--
MANDATORY PHASE ORDER:
  A → Config & Data Model (foundation — no dependencies)
  B → New Effect Handlers (depends on A)
  C → Buff System Integration (depends on B, skip if no new buff types)
  D → AI Behavior (depends on B)
  E → Frontend Integration (depends on A, can parallel with C/D)
  F → Particle Effects & Audio (depends on E)
  G → Sprite Integration (optional, last)

If the class introduces NO new effect types:
  - Phase B becomes "Skill Wiring" (just dispatcher entries for existing handlers)
  - Phase C can be skipped entirely
  - Total phases may be A, B, D, E, F, G (or even fewer)

CRITICAL RULES FOR EACH PHASE:
  1. List EVERY file that will be modified
  2. Show the EXACT config/code to add (copy-pasteable)
  3. List SPECIFIC tests with descriptions (not vague "test it works")
  4. Provide estimated test count
  5. After implementing, run full test suite to verify zero regressions
-->

### Phase {N}A — Config & Data Model (Foundation)

**Goal:** Add {ClassName} to classes and skills configs. Wire up the data layer. Zero logic changes.

**Files Modified:**
| File | Change |
|------|--------|
| `server/configs/classes_config.json` | Add `{class_id}` class definition |
| `server/configs/skills_config.json` | Add {X} skills + `class_skills.{class_id}` mapping |

**Config: `classes_config.json`**
```json
"{class_id}": {
  "class_id": "{class_id}",
  "name": "{ClassName}",
  "role": "{Role}",
  "description": "{Grimdark description, 1-2 sentences.}",
  "base_hp": {hp},
  "base_melee_damage": {melee},
  "base_ranged_damage": {ranged},
  "base_armor": {armor},
  "base_vision_range": {vision},
  "ranged_range": {range},
  "allowed_weapon_categories": [{categories}],
  "color": "{#hex}",
  "shape": "{shape}"
}
```

**Config: `skills_config.json`** — {X} new skills:
```json
{Paste the COMPLETE JSON for each skill definition. Do NOT abbreviate.}
```

**`class_skills` mapping:**
```json
"{class_id}": ["{auto_attack_type}", "{skill_1_id}", "{skill_2_id}", "{skill_3_id}", "{skill_4_id}"]
```

**Tests (Phase {N}A):**
- {ClassName} class loads from config with correct stats
- All {X} skills load from config with correct properties
- `class_skills["{class_id}"]` maps to correct 5 skills
- `can_use_skill()` validates {ClassName} skills for {class_id} class
- `can_use_skill()` rejects {ClassName} skills for non-{class_id} classes
- Existing class tests still pass (regression check)

**Estimated tests:** 8–10

**Post-phase gate:** Run `pytest server/tests/` — ALL tests must pass before proceeding.

---

### Phase {N}B — Effect Handlers (Core Mechanics)

<!-- 
If ALL skills use existing effect types, this phase is simpler:
- Just add dispatcher branches in resolve_skill_action()
- Possibly add minor targeting variants
- Test that each skill resolves correctly through the existing handlers

If NEW effect types are needed, follow the Bard pattern:
- Implement each handler as a standalone function
- Add dispatcher branches
- Test extensively (8-10 tests per new handler)
-->

**Goal:** {Implement N new effect type handlers / Wire N skills to existing handlers} and connect them to the `resolve_skill_action()` dispatcher.

**Files Modified:**
| File | Change |
|------|--------|
| `server/app/core/skills.py` | {Add handlers / Add dispatcher branches} |
| `server/app/core/turn_phases/skills_phase.py` | {If skills_phase dispatcher needs updating} |

#### Handler {X}: `resolve_{type}()` (~{N} lines)

```
Input:  {parameter list}
Logic:  1. {Step 1}
        2. {Step 2}
        3. {Step 3}
        4. {Step 4}
Output: ActionResult with {description}
```

#### Dispatcher Update

```python
# Add to resolve_skill_action():
elif effect_type == "{new_type}":
    return resolve_{new_type}(player, action, skill_def, players, ...)
```

**Tests (Phase {N}B):**

<!-- List EVERY test. Be specific. Each test = one assertion about one behavior. -->

*{Skill 1 Name} ({effect_type}):*
- {Test description 1}
- {Test description 2}
- {Test description 3}
- {... enough to cover: happy path, edge cases, failures, cooldown, targeting validation}

*{Skill 2 Name} ({effect_type}):*
- {Test description 1}
- {... etc}

*{Repeat for each skill}*

**Estimated tests:** {N}

**Post-phase gate:** Run `pytest server/tests/` — ALL tests must pass.

---

### Phase {N}C — Buff System Integration (if applicable)

<!-- 
SKIP THIS PHASE if the class introduces no new buff/debuff stat types.
Write: "Phase {N}C — Skipped (no new buff types)"

INCLUDE THIS PHASE if any skill creates a buff/debuff with a NEW stat name
that must be checked in the combat damage pipeline.
-->

**Goal:** Wire new buff/debuff stats into the damage calculation pipeline so they actually affect combat.

**Files Modified:**
| File | Change |
|------|--------|
| {file} | {change description} |

#### {stat_name} Integration

{Show exactly which functions need modification and the code to add.}

**Tests (Phase {N}C):**

*{stat_name}:*
- {Test: buff/debuff affects melee damage}
- {Test: buff/debuff affects ranged damage}
- {Test: buff/debuff affects skill damage}
- {Test: multiplier expires when buff ticks down}
- {Test: stacks correctly with existing multipliers}
- {Test: minimum damage still 1}

**Estimated tests:** {N}

**Post-phase gate:** Run `pytest server/tests/` — ALL tests must pass.

---

### Phase {N}D — AI Behavior ({ai_role} role)

**Goal:** Implement AI decision-making so {ClassName} AI heroes and AI-controlled {ClassName}s play intelligently.

**Files Modified:**
| File | Change |
|------|--------|
| `server/app/core/ai_skills.py` | Add `"{class_id}": "{ai_role}"` to `_CLASS_ROLE_MAP` |
| `server/app/core/ai_skills.py` | Add `_{ai_role}_skill_logic()` function (if new role) |
| `server/app/core/ai_skills.py` | Add `"{ai_role}"` branch to dispatcher (if new role) |

<!-- If reusing an existing AI role, this phase is minimal — just the _CLASS_ROLE_MAP entry. -->

#### AI Decision Logic

```python
def _{ai_role}_skill_logic(ai, enemies, all_units, grid_w, grid_h, obstacles):
    """{Brief description of AI strategy}"""

    # 1. {Highest priority — condition}
    # 2. {Second priority — condition}
    # 3. {Third — condition}
    # 4. {Fourth — condition}
    # 5. Fallback — auto-attack
    return None
```

**Tests (Phase {N}D):**
- {ClassName} AI uses {skill 1} when {condition}
- {ClassName} AI skips {skill 1} when {negative condition}
- {ClassName} AI uses {skill 2} when {condition}
- {ClassName} AI falls back to auto-attack when all skills on cooldown
- {ClassName} AI positioning {expected behavior}
- {... etc}

**Estimated tests:** 8–12

**Post-phase gate:** Run `pytest server/tests/` — ALL tests must pass.

---

### Phase {N}E — Frontend Integration (Rendering + UI)

**Goal:** Add {ClassName} to the client — shape rendering, class selection, colors, icons, inventory portrait.

**Files Modified:**
| File | Change |
|------|--------|
| `client/src/canvas/renderConstants.js` | Add {class_id} to `CLASS_COLORS`, `CLASS_SHAPES`, `CLASS_NAMES` |
| `client/src/canvas/unitRenderer.js` | Add `{shape}` shape rendering case |
| `client/src/components/WaitingRoom/WaitingRoom.jsx` | Add {shape} icon to shape map |
| `client/src/components/Inventory/Inventory.jsx` | Add {shape} SVG path to `CLASS_SHAPE_PATHS` |
| `client/src/components/Inventory/Inventory.jsx` | Add skill buff names to `formatBuffName` / `formatBuffEffect` (if new buffs) |

#### renderConstants.js additions

```javascript
// CLASS_COLORS
{class_id}: '{#hex}',

// CLASS_SHAPES
{class_id}: '{shape}',

// CLASS_NAMES
{class_id}: '{ClassName}',
```

#### unitRenderer.js — {Shape} Shape

```javascript
case '{shape}': {
  // {Description of what the shape looks like}
  ctx.beginPath();
  {... canvas drawing code ...}
  ctx.closePath();
  ctx.fill();
  ctx.stroke();
  break;
}
```

#### WaitingRoom.jsx — Shape icon

```
cls.shape === '{shape}' ? '{unicode_icon}' : ...
```

#### Inventory.jsx — SVG portrait path

```javascript
{shape}: <path d="{svg_path_data}" />,
```

#### Inventory.jsx — Buff name formatting (if new buff types)

```javascript
// formatBuffName:
{skill_id}: '{Skill Display Name}',

// formatBuffEffect (if new buff stats):
if (buff.stat === '{stat_name}') return `{display format}`;
```

**Tests (Phase {N}E):** Visual verification — manual checklist:
- [ ] {ClassName} appears in class selection screen
- [ ] {Shape} shape renders correctly on canvas
- [ ] Color ({#hex}) displays correctly and is distinguishable
- [ ] {ClassName} name shows in nameplate
- [ ] Inventory portrait shows {shape}
- [ ] Buff/debuff icons display correctly in HUD (if applicable)
- [ ] Skill icons appear in bottom bar with correct names

---

### Phase {N}F — Particle Effects & Audio (Polish)

**Goal:** Add visual and audio feedback for {ClassName} skills.

**Files Modified:**
| File | Change |
|------|--------|
| `client/public/particle-presets/skills.json` | Add {class_id} skill effects |
| `client/public/particle-presets/buffs.json` | Add buff auras (if applicable) |
| `client/public/audio-effects.json` | Add {class_id} audio triggers |
| `client/src/audio/soundMap.js` | Add {class_id} sound mappings |

#### Particle Effects

| Skill | Particle Effect | Description |
|-------|----------------|-------------|
| {Skill 1} | `{effect-id}` | {Brief visual description} |
| {Skill 2} | `{effect-id}` | {Brief visual description} |
| {Skill 3} | `{effect-id}` | {Brief visual description} |
| {Skill 4} | `{effect-id}` | {Brief visual description} |

#### Audio

| Skill | Sound | Category |
|-------|-------|----------|
| {Skill 1} | {Brief description of sound} | skills |
| {Skill 2} | {Brief description of sound} | skills |
| {Skill 3} | {Brief description of sound} | skills |
| {Skill 4} | {Brief description of sound} | skills |

**Tests (Phase {N}F):** Manual verification only.
- [ ] Each skill triggers correct particle effect
- [ ] Buff auras visible on affected units (if applicable)
- [ ] Audio plays on skill use
- [ ] No console errors from missing assets

---

### Phase {N}G — Sprite Integration (Optional)

**Goal:** Add {ClassName} sprite variants from the character sheet atlas.

**Files Modified:**
| File | Change |
|------|--------|
| `client/src/canvas/SpriteLoader.js` | Add {class_id} sprite variants |

*This phase depends on finding suitable sprites in the existing atlas. If no {class_id}-appropriate sprites exist, the {shape} shape fallback works perfectly.*

---

## Implementation Order & Dependencies

```
Phase {N}A (Config)           ← No dependencies, pure data
    ↓
Phase {N}B (Effect Handlers)  ← Depends on {N}A (needs skill definitions)
    ↓
Phase {N}C (Buff Integration) ← Depends on {N}B (skip if no new buff types)
    ↓
Phase {N}D (AI Behavior)      ← Depends on {N}B (needs handlers working)
    ↓
Phase {N}E (Frontend)         ← Depends on {N}A — can parallel with {N}C/{N}D
    ↓
Phase {N}F (Polish)           ← Depends on {N}E (needs rendering working)
    ↓
Phase {N}G (Sprites)          ← Optional, last
```

**Parallelizable:** {N}C + {N}D can run in parallel after {N}B. {N}E can start after {N}A.

---

## Test Summary

| Phase | Test Count | Focus |
|-------|:----------:|-------|
| {N}A — Config | 8–10 | Class/skill loading, validation |
| {N}B — Effect Handlers | {N} | Handler logic, edge cases |
| {N}C — Buff Integration | {N} | Damage multipliers in combat pipeline |
| {N}D — AI Behavior | 8–12 | AI decision logic |
| {N}E — Frontend | 0 (manual) | Visual verification |
| {N}F — Polish | 0 (manual) | Particles, audio |
| **Total** | **{N}** | |

---

## Tuning Levers

<!-- List every numeric value that can be adjusted for balance. This is the post-launch tuning guide. -->

| Parameter | Initial Value | Reduce If... | Increase If... |
|-----------|:------------:|--------------|----------------|
| {Stat/skill parameter} | {value} | {When would you decrease} | {When would you increase} |
| {... repeat for each tunable value ...} | | | |

### Known Balance Risks

<!-- List 2-4 specific balance concerns. Be honest about potential problems. -->

1. **{Risk 1}:** {Description of the risk and potential mitigation}
2. **{Risk 2}:** {Description and mitigation}
3. **{Risk 3}:** {Description and mitigation}

---

## Future Enhancements (Post-Phase {N})

<!-- Ideas that are explicitly OUT OF SCOPE for this phase but worth noting for later. -->

- **{Enhancement 1}:** {Brief description}
- **{Enhancement 2}:** {Brief description}
- **{Enhancement 3}:** {Brief description}

---

## Phase Checklist

<!-- Copy this and check items off as you complete them. This is the implementation tracker. -->

- [ ] **{N}A** — {ClassName} added to `classes_config.json`
- [ ] **{N}A** — {X} skills added to `skills_config.json`
- [ ] **{N}A** — `class_skills.{class_id}` mapping added
- [ ] **{N}A** — Config loading tests pass
- [ ] **{N}B** — {List each new handler or dispatcher branch}
- [ ] **{N}B** — `resolve_skill_action()` dispatcher updated
- [ ] **{N}B** — All handler tests pass
- [ ] **{N}C** — {List each integration point, or "Skipped — no new buff types"}
- [ ] **{N}C** — Buff integration tests pass
- [ ] **{N}D** — AI role implemented
- [ ] **{N}D** — `_CLASS_ROLE_MAP` updated
- [ ] **{N}D** — AI behavior tests pass
- [ ] **{N}E** — `renderConstants.js` updated
- [ ] **{N}E** — {Shape} shape renders in `unitRenderer.js`
- [ ] **{N}E** — WaitingRoom class select shows {ClassName}
- [ ] **{N}E** — Inventory portrait & buff names updated
- [ ] **{N}F** — Particle effects added
- [ ] **{N}F** — Audio triggers added
- [ ] **{N}G** — Sprite variants mapped (or skipped)
- [ ] Balance pass after playtesting

---

## Post-Implementation Cleanup

After all phases complete:

1. **Update `README.md`:**
   - Add {ClassName} to the class count in the Features table
   - Add phase {N} to the Documentation → Phase Specs list
   - Update the status line at the top
   - Update the test count

2. **Update `docs/Current Phase.md`:**
   - Add phase {N} milestone entry with test counts

3. **Update `docs/Game stats references/game-balance-reference.md`:**
   - Add {ClassName} stat block

4. **Final test run:**
   - `pytest server/tests/` — ALL tests pass, zero failures
   - Record final test count

---

**Document Version:** 1.0
**Created:** {date}
**Status:** Not Started
**Prerequisites:** {Previous phase} Complete
