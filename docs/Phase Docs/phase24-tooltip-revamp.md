# Phase 24 — Skill Tooltip Revamp

**Created:** March 2026
**Status:** Phase 24A + 24B + 24C + 24D + 24E Complete
**Previous:** Phase 23 (Plague Doctor Class)
**Goal:** Overhaul skill/ability tooltips from flat, hard-to-read text dumps into clear, visually structured panels with proper information hierarchy, computed damage estimates, complete effect coverage, and distinct separation between mechanics and flavor text.

---

## Overview

The current `SkillTooltip` component has several readability problems:

1. **Italic description looks like a quote** — `.skill-tooltip-desc` uses `font-style: italic` + `font-family: var(--font-flavor)` which makes functional descriptions ("Deal 24 holy damage") appear as narrative flavor text
2. **Flat information dump** — Name, targeting, cooldown, effects, description, and hotkey are listed with no visual grouping or section dividers
3. **Missing effect types** — `formatEffect()` only handles 10 of 20+ effect types; newer skills (stun, AoE damage, lifesteal, conditional buffs, debuffs, cleanse, etc.) fall through to `default` and render as raw type strings
4. **No damage estimates** — Players see "1.8× ranged damage" but have no idea what that means in actual HP; the player's stats are available and we can compute approximate numbers
5. **Description redundancy** — The config `description` field often repeats exactly what the formatted effects already show, wasting tooltip space
6. **Hotkey buried at bottom** — The hotkey hint is hidden in a footer line when it could be a clean badge next to the name

---

## Architecture

### Files Modified

| File | Change |
|------|--------|
| `client/src/components/BottomBar/SkillTooltip.jsx` | Major rewrite — new layout, all effect types, damage estimates |
| `client/src/styles/components/_bottom-bar.css` | Tooltip CSS overhaul — sections, dividers, accent colors, no italic |
| `server/configs/skills_config.json` | Add `flavor` field to skills that have genuine flavor text; clean up `description` to be mechanical-only |

### No New Files Required

All changes are modifications to existing files. The tooltip is self-contained in `SkillTooltip.jsx` with styles in `_bottom-bar.css` and data from `skills_config.json`.

---

## Implementation Phases

### Phase 24A — Complete Effect Formatting (Quick Win)

**Goal:** Make `formatEffect()` handle every effect type in `skills_config.json` so no skill tooltip shows a raw type string.

**Changes: `SkillTooltip.jsx` — `formatEffect()` function**

Add cases for all unhandled effect types:

```
Effect Type             → Formatted String
─────────────────────── ─────────────────────────────────────────────
stun_damage             → "X% melee damage + stun for Y turn(s)"
aoe_heal                → "Heals all allies within X tile(s) for Y HP"
aoe_damage              → "X% damage to all enemies within Y tile(s) of target"
aoe_damage_slow         → "X damage + slow all enemies within Y tile(s) for Z turn(s)"
aoe_damage_slow_targeted→ "X damage + slow all enemies within Y tile(s) of target for Z turn(s)"
aoe_buff                → "+X% stat to all allies within Y tile(s) for Z turn(s)"
aoe_debuff              → "All enemies within X tile(s) ... for Y turn(s)"
magic_damage            → "X× magic damage"
lifesteal_damage        → "X% melee damage, heal Y% of damage dealt"
lifesteal_aoe           → "X% damage to all enemies within Y tile(s), heal Z% of total"
conditional_buff        → "If below X% HP: heal Y HP, +Z% stat for W turn(s)"
buff_cleanse            → "+X stat for Y turn(s), cleanses DoT effects"
cooldown_reduction      → "Reduce all skill cooldowns by X turn(s)"
damage_absorb           → "Absorbs next X damage (Y turn(s))"
evasion                 → "Dodge next X attack(s) (up to Y turn(s))"
taunt                   → "Force enemies within X tile(s) to target you for Y turn(s)"
passive_enrage          → "Below X% HP: +Y% melee damage (permanent)"
passive_aura_ally_buff  → "+X stat to nearby tag allies within Y tile(s)"
```

**Validation:**
- [x] Every skill in `skills_config.json` has its effects formatted as readable text
- [x] No tooltip shows a raw effect type string (e.g., "aoe_damage_slow")
- [x] Existing formatted effects (melee_damage, ranged_damage, heal, hot, dot, buff, shield_charges, teleport, detection) unchanged
- [x] Also fixed `hot` handler to support both `heal_per_tick` and `heal_per_turn` field names (crimson_veil uses `heal_per_turn`)
- [x] Added `ranged_damage_slow` handler (crippling_shot) — not in original spec but found in config

**Completed:** March 6, 2026 — 19 new effect type cases added to `formatEffect()`

---

### Phase 24B — Fix Italic / Description Confusion

**Goal:** Remove the italic flavor-text styling from mechanical descriptions and create proper visual separation.

**Changes: `_bottom-bar.css`**

Before (current):
```css
.skill-tooltip-desc {
  font-size: 0.7rem;
  color: var(--text-secondary);
  font-family: var(--font-flavor);
  font-style: italic;
  margin-bottom: 0.2rem;
  line-height: 1.35;
}
```

After:
```css
/* Mechanical description — clear, readable, NOT italic */
.skill-tooltip-desc {
  font-size: 0.72rem;
  color: var(--text-secondary);
  font-family: var(--font-body);
  font-style: normal;
  margin-bottom: 0.2rem;
  line-height: 1.4;
}

/* Optional flavor text — italic, dimmer, clearly separated */
.skill-tooltip-flavor {
  font-size: 0.65rem;
  color: var(--text-dim);
  font-family: var(--font-flavor);
  font-style: italic;
  margin-top: 0.25rem;
  line-height: 1.3;
  opacity: 0.8;
}
```

**Changes: `SkillTooltip.jsx`**

- Render `skill.description` in `.skill-tooltip-desc` (non-italic, normal font)
- Render `skill.flavor` (if present) in a new `.skill-tooltip-flavor` div below the description

**Validation:**
- [x] Descriptions render in normal body font, not italic
- [x] Flavor text (where present) is clearly visually distinct — dimmer, italic, smaller
- [x] Skills without a `flavor` field show no empty flavor div

**Completed:** March 6, 2026 — CSS updated, `.skill-tooltip-flavor` class added, JSX renders both `description` and `flavor`

---

### Phase 24C — Tooltip Layout Restructure

**Goal:** Reorganize the tooltip into clearly separated visual sections with dividers and a better information hierarchy.

**New tooltip structure:**

```
┌──────────────────────────────────┐
│ 🔥 Fireball                 [2] │  Header: icon + name + hotkey badge
│ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ │  Subtle divider
│ Enemy (Ranged) · Range 5 · LOS  │  Targeting line
│ Cooldown: 5 turns      (ready)  │  Cooldown status
│ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ │  Subtle divider
│ ● 2.0× magic damage             │  Effects section
│ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ │  Subtle divider
│ Hurl a bolt of fire at an enemy  │  Mechanical description
│ for 2.0x ranged damage.         │
│                                  │
│ The Mage's bread-and-butter nuke │  Flavor text (dim, italic)
└──────────────────────────────────┘
```

**Changes: `SkillTooltip.jsx`**

- Move hotkey badge into the header row (next to skill name, right-aligned)
- Remove the standalone `skill-tooltip-hint` footer section
- Add `<div className="skill-tooltip-divider" />` between the three main sections: header, stats/effects, description
- Group targeting + cooldown together as the "stats" section
- Group effects as the "effects" section
- Group description + flavor as the "info" section

**Changes: `_bottom-bar.css`**

Add new CSS rules:

```css
/* Tooltip header row: name left, hotkey badge right */
.skill-tooltip-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 0.2rem;
}

/* Hotkey badge in header */
.skill-tooltip-hotkey-badge {
  font-size: 0.6rem;
  color: var(--text-dim);
  background: rgba(255, 255, 255, 0.06);
  border: 1px solid var(--border-dark);
  border-radius: 2px;
  padding: 0.1rem 0.35rem;
  font-family: var(--font-body);
  line-height: 1;
}

/* Subtle section dividers */
.skill-tooltip-divider {
  height: 1px;
  background: var(--border-dark);
  margin: 0.35rem 0;
  opacity: 0.5;
}
```

**Validation:**
- [x] Hotkey appears as a badge next to the name (right-aligned)
- [x] Three clear visual sections separated by dividers
- [x] No more standalone "Hotkey: X" footer line
- [x] PotionTooltip also updated to match the new structure
- [x] Tooltip still clamps to viewport edges correctly

**Completed:** March 6, 2026 — Header row with hotkey badge, 3 divider-separated sections (stats, effects, info), `.skill-tooltip-hint` removed and replaced by `.skill-tooltip-hotkey-badge`, PotionTooltip restructured to match

---

### Phase 24D — Computed Damage Estimates

**Goal:** Show approximate damage numbers based on the active unit's stats, so players understand their actual output.

**Changes: `SkillTooltip.jsx`**

- Accept a new prop: `attackerStats` (the active unit's stats object: `{ attack_damage, ranged_damage, armor, ... }`)
- Add a `computeDamageEstimate(effect, attackerStats)` helper that returns a number or null
- Display estimates inline with effects using a dimmer style:

```
● 1.8× ranged damage (~31 dmg)
● 2 hits × 60% melee damage (~18 per hit)
● Heals 30 HP
● 8 damage/turn for 4 turns (32 total)
```

**Damage computation logic:**

| Effect Type | Estimate Formula |
|-------------|-----------------|
| `melee_damage` | `Math.round(attackerStats.attack_damage × multiplier × hits)` per hit |
| `ranged_damage` | `Math.round(attackerStats.ranged_damage × multiplier)` |
| `magic_damage` | `Math.round(attackerStats.ranged_damage × multiplier)` |
| `holy_damage` | Use `base_damage` directly (already absolute) |
| `stun_damage` | `Math.round(attackerStats.attack_damage × multiplier)` + stun info |
| `lifesteal_damage` | `Math.round(attackerStats.attack_damage × multiplier)` + heal % |
| `aoe_damage` | `Math.round(attackerStats.ranged_damage × multiplier)` per target |
| `dot` | Already shows absolute numbers — no change |
| `heal` / `hot` | Already shows absolute numbers — no change |

**Changes: `BottomBar.jsx`**

- Pass `attackerStats` prop to `<SkillTooltip>`:
  ```jsx
  <SkillTooltip
    skill={skill}
    hotkey={String(index + 1)}
    cooldown={cooldown}
    isAutoAttack={isAutoAttack}
    attackerStats={{
      attack_damage: activeUnit?.attack_damage || 0,
      ranged_damage: activeUnit?.ranged_damage || 0,
    }}
  />
  ```

**Changes: `_bottom-bar.css`**

```css
/* Inline damage estimate next to effect line */
.skill-tooltip-estimate {
  color: var(--text-dim);
  font-size: 0.65rem;
  margin-left: 0.3rem;
}
```

**Validation:**
- [x] Melee skills show approximate per-hit damage based on `attack_damage`
- [x] Ranged/magic skills show approximate damage based on `ranged_damage`
- [x] Multi-hit skills show per-hit and total estimates
- [x] DoTs and heals (already absolute) show no redundant estimate
- [x] Estimates labeled clearly as approximate (use `~` prefix)
- [x] If `attackerStats` not available (e.g., loading), estimates gracefully omitted
- [x] Also handles `ranged_damage_slow` and `lifesteal_aoe` estimate types

**Completed:** March 6, 2026 — `computeDamageEstimate()` helper added (8 effect types), `attackerStats` prop wired from BottomBar, `.skill-tooltip-estimate` CSS added

---

### Phase 24E — Config Cleanup: Description vs. Flavor Split

**Goal:** Clean up `skills_config.json` so `description` contains only mechanical info and a new optional `flavor` field contains thematic text.

**Changes: `server/configs/skills_config.json`**

For each skill, audit the `description` field:

| Skill | Current Description | New Description | New Flavor |
|-------|-------------------|-----------------|------------|
| `auto_attack_melee` | "Basic melee attack. Pursue and strike an adjacent enemy." | "Basic melee attack." | "Pursue and strike an adjacent enemy." |
| `auto_attack_ranged` | "Basic ranged attack. Pursue and shoot enemies within range." | "Basic ranged attack." | "Pursue and shoot enemies within range." |
| `heal` | "Restore HP to yourself or a nearby ally." | "Restore HP to yourself or a nearby ally." | *(none)* |
| `double_strike` | "Strike an adjacent enemy twice at 60% damage each hit." | "Strike an adjacent enemy twice at 60% damage each hit." | *(none)* |
| `power_shot` | "A devastating ranged attack at 1.8x damage. Longer cooldown than normal ranged." | "Ranged attack at 1.8× damage." | "A devastating shot that pierces through armor." |
| `war_cry` | "Buff yourself — next melee attack deals 2x damage. Lasts 2 turns." | "Buff self — 2× melee damage for 2 turns." | *(none)* |
| `shadow_step` | "Teleport to a tile within 3 range (must be unoccupied, must have LOS)." | "Teleport to an unoccupied tile within range." | "Step through the shadows to reposition instantly." |
| `wither` | "Curse an enemy — deal 8 damage per turn for 4 turns (32 total). Recasting refreshes duration." | "8 damage/turn for 4 turns. Recasting refreshes duration." | "A creeping curse that rots the flesh." |
| `ward` | "Gain 3 charges. When attacked, attacker takes 8 reflected damage and 1 charge is consumed." | "Gain 3 charges. Attackers take 8 reflected damage per hit." | *(none)* |
| `divine_sense` | "Reveal all Undead and Demon enemies within 12 tiles for 4 turns." | "Reveal Undead and Demon enemies within 12 tiles for 4 turns." | "Your faith illuminates the wicked." |
| `fireball` | "Hurl a bolt of fire at an enemy for 2.0x ranged damage. The Mage's bread-and-butter nuke." | "2.0× magic damage to target enemy." | "The Mage's bread-and-butter nuke." |
| `frost_nova` | "Blast frost around you — deal 12 damage and slow all enemies within 2 tiles for 2 turns." | "12 damage + slow to all enemies within 2 tiles for 2 turns." | "A blast of freezing air erupts from the caster." |
| `arcane_barrage` | "Rain arcane energy on an area — deal 1.0x ranged damage to all enemies within 1 tile of target." | "1.0× damage to all enemies within 1 tile of target." | "Arcane missiles rain from the sky." |
| `blink` | "Teleport to an unoccupied tile within 4 range. Essential escape tool for the fragile Mage." | "Teleport to an unoccupied tile within 4 range." | "Essential escape tool for the fragile Mage." |
| `taunt` | "Force all nearby enemies within 2 tiles to target you for 2 turns." | "Force enemies within 2 tiles to target you for 2 turns." | *(none)* |
| `shield_bash` | "Slam an adjacent enemy with your shield — deals 0.7x melee damage and stuns for 1 turn." | "0.7× melee damage + stun for 1 turn." | "A brutal shield slam that staggers the target." |
| `holy_ground` | "Consecrate the ground around you — heal all allies within 1 tile for 15 HP." | "Heal all allies within 1 tile for 15 HP." | "Consecrated ground burns the unholy." |
| `bulwark` | "Brace yourself — gain +8 armor for 4 turns." | "+8 armor for 4 turns." | "An unbreakable stance of pure defense." |
| `volley` | "Rain arrows on an area — deal 0.5x ranged damage to all enemies within 2 tiles of target." | "0.5× ranged damage to all enemies within 2 tiles of target." | "A hail of arrows darkens the sky." |
| `evasion` | "Enter a defensive stance — dodge the next 2 attacks. Lasts up to 4 turns." | "Dodge the next 2 attacks (up to 4 turns)." | "A blur of motion — the Ranger vanishes from sight." |
| `crippling_shot` | "A precise shot that deals 0.8x ranged damage and slows the target for 2 turns (cannot move)." | "0.8× ranged damage + slow for 2 turns." | "A precise shot to the knee cripples movement." |
| `shield_of_faith` | "Grant an ally or self +5 armor for 3 turns." | "+5 armor to ally or self for 3 turns." | *(none)* |
| `exorcism` | "Deal 20 holy damage (40 vs Undead/Demons). 5-tile range." | "20 holy damage (40 vs Undead/Demons)." | "The power of faith made manifest." |
| `prayer` | "Heal over time — restore 8 HP per turn for 4 turns (32 total) to self or ally." | "8 HP/turn for 4 turns (32 total) to ally or self." | "A whispered prayer that mends the faithful." |
| `rebuke` | "Deal 24 holy damage (36 vs Undead/Demons). 6-tile range." | "24 holy damage (36 vs Undead/Demons)." | "Judgement falls upon the wicked." |
| `ballad_of_might` | "Sing a war hymn — all allies within 2 tiles gain +30% melee and ranged damage for 3 turns." | "+30% damage to all allies within 2 tiles for 3 turns." | "A hymn of war that stirs the blood." |
| `dirge_of_weakness` | "Chant a dirge of doom — all enemies within 2 tiles of target take 25% more damage for 3 turns." | "+25% damage taken by all enemies within 2 tiles of target for 3 turns." | "A dirge of inevitable doom." |
| `verse_of_haste` | "Accelerate an ally's recovery — reduce all skill cooldowns by 2 turns." | "Reduce all skill cooldowns by 2 turns for target ally or self." | "Time itself bends to the melody." |
| `cacophony` | "Unleash a deafening shriek — deal 10 damage and slow all enemies within 2 tiles for 2 turns." | "10 damage + slow to all enemies within 2 tiles for 2 turns." | "An ear-splitting shriek that shatters concentration." |
| `blood_strike` | "A vampiric strike — deal 1.4x melee damage and heal yourself for 40% of damage dealt." | "1.4× melee damage + heal 40% of damage dealt." | "Drink deep of the enemy's lifeblood." |
| `crimson_veil` | "Shroud yourself in stolen vitality — gain +30% melee damage and heal 6 HP/turn for 3 turns." | "+30% melee damage + 6 HP/turn for 3 turns." | "Stolen vitality cloaks the Blood Knight in crimson mist." |
| `sanguine_burst` | "Erupt in a fountain of stolen blood — deal 0.7x melee damage to all enemies within 1 tile and heal for 50% of total damage dealt." | "0.7× melee damage to enemies within 1 tile + heal 50% of total." | "A fountain of stolen blood erupts." |
| `blood_frenzy` | "Channel your wounds into rage — if below 40% HP, instantly heal 15 HP and gain +50% melee damage for 3 turns." | "If below 40% HP: heal 15 HP + 50% melee damage for 3 turns." | "Pain becomes power. Wounds become wrath." |
| `miasma` | "Lob a toxic cloud at a target area — deal 10 magic damage and slow all enemies within 2 tiles for 2 turns." | "10 damage + slow to all enemies within 2 tiles of target for 2 turns." | "A noxious cloud of plague and misery." |
| `plague_flask` | "Hurl a vial of pestilence at an enemy — deal 7 poison damage per turn for 4 turns (28 total). Recasting refreshes duration." | "7 damage/turn for 4 turns (28 total). Recasting refreshes." | "A vial of concentrated pestilence shatters on impact." |
| `enfeeble` | "Release a cloud of enervating toxin — all enemies within 2 tiles of target deal 25% less damage for 3 turns." | "-25% damage dealt by enemies within 2 tiles of target for 3 turns." | "Toxic fumes sap the will to fight." |
| `inoculate` | "Administer an antitoxin — grant ally or self +3 armor for 3 turns and cleanse all active poison/DoT effects." | "+3 armor for 3 turns + cleanse all DoTs on ally or self." | "The doctor's cure cuts through corruption." |

**Rules for the split:**
1. `description` = concise mechanical summary (what the skill does in game terms)
2. `flavor` = optional thematic/lore text (how it feels, grimdark atmosphere)
3. If the original is already purely mechanical, leave `description` as-is and add no `flavor`
4. If the original mixes both, extract the thematic part into `flavor`

**Validation:**
- [x] Every skill has a clean, mechanical `description`
- [x] Skills with genuine flavor text have a `flavor` field
- [x] No `description` contains both mechanical info and thematic prose
- [x] Server tests still pass (3251 tests, 0 failures — the `flavor` field is cosmetic, no backend logic uses `description`)
- [x] Client renders both fields correctly (Phase 24B already handled the CSS)
- [x] Also cleaned up enemy-only skills (venom_gaze, soul_reap, bone_shield, dark_pact, profane_ward) — same description/flavor split rules applied
- [x] 44 total skills in config: 36 with `flavor` field, 8 purely mechanical (no flavor needed)

**Completed:** March 6, 2026 — All 44 skill descriptions cleaned to concise mechanical text, 36 `flavor` fields added, JSON validated, 3251 tests passing

---

## Phase Summary & Dependency Order

```
Phase 24A — Complete Effect Formatting
  └─ No dependencies. Can be done first.
  └─ Files: SkillTooltip.jsx only

Phase 24B — Fix Italic / Description Confusion
  └─ No dependencies. Can be done first (or parallel with 24A).
  └─ Files: _bottom-bar.css, SkillTooltip.jsx

Phase 24C — Tooltip Layout Restructure
  └─ Depends on 24B (uses the new desc/flavor split CSS)
  └─ Files: SkillTooltip.jsx, _bottom-bar.css

Phase 24D — Computed Damage Estimates
  └─ Depends on 24A (needs all effect types formatted) and 24C (needs new layout)
  └─ Files: SkillTooltip.jsx, BottomBar.jsx, _bottom-bar.css

Phase 24E — Config Cleanup
  └─ Depends on 24B (needs flavor rendering support in place)
  └─ Files: skills_config.json
```

**Recommended execution order:** 24A → 24B → 24C → 24D → 24E

Phases A and B can be done in parallel since they touch different parts of the code. Phase C builds on B's CSS. Phase D needs A's effect formatting and C's layout. Phase E is a data-only change that needs B's flavor rendering.

---

## Testing Strategy

### Manual Testing Checklist

Each phase should be verified by hovering every skill slot in the bottom bar:

- [ ] **Crusader:** Auto Attack, Taunt, Shield Bash, Holy Ground, Bulwark
- [ ] **Confessor:** Auto Attack, Heal, Shield of Faith, Exorcism, Prayer
- [ ] **Inquisitor:** Auto Attack, Power Shot, Shadow Step, Divine Sense, Rebuke
- [ ] **Ranger:** Auto Attack (ranged), Power Shot, Volley, Evasion, Crippling Shot
- [ ] **Hexblade:** Auto Attack, Double Strike, Shadow Step, Wither, Ward
- [ ] **Mage:** Auto Attack (ranged), Fireball, Frost Nova, Arcane Barrage, Blink
- [ ] **Bard:** Auto Attack (ranged), Ballad of Might, Dirge of Weakness, Verse of Haste, Cacophony
- [ ] **Blood Knight:** Auto Attack, Blood Strike, Crimson Veil, Sanguine Burst, Blood Frenzy
- [ ] **Plague Doctor:** Auto Attack (ranged), Miasma, Plague Flask, Enfeeble, Inoculate
- [ ] **Potion tooltip** still renders correctly
- [ ] **Cooldown states** display correctly (on cooldown vs. ready)
- [ ] **Edge cases:** Tooltip doesn't overflow viewport left/right, tooltip disappears on mouse leave

### Automated

- Run existing test suite (`2933+ tests`) to confirm no regressions
- The tooltip is purely a client rendering concern — server-side tests should be unaffected
- Verify `skills_config.json` is still valid JSON after Phase 24E edits

---

## Risk Assessment

| Risk | Mitigation |
|------|-----------|
| Breaking tooltip for skills with unusual effect combos | Phase 24A adds explicit handlers for every type; `default` case remains as safety net |
| Damage estimates being misleading (armor not factored) | Label as "~X dmg" with `~` prefix; add "(before armor)" suffix if space permits |
| `flavor` field not loaded by client | The client already receives the full skill object from `skills_config` — new fields pass through automatically |
| Layout changes breaking on very small viewports | Existing `clampTooltipRef` logic handles viewport edge clamping; tooltip `max-width: 280px` stays |
| Config editing risk (24E is a big JSON diff) | Phase 24E is data-only — validate JSON after each edit, run server tests |

---

## Out of Scope

- **Item/gear tooltips** — Those use a separate tooltip system and are not part of this phase
- **Enemy panel skill display** — The enemy panel shows enemy skills differently; may be a future phase
- **Mana costs** — All skills currently have `mana_cost: 0`; when mana is implemented, the tooltip will need a mana line (future phase)
- **Skill icon overhaul** — The `SkillIcon` component and sprite sheet are separate from tooltip content
- **Localization** — All text is currently English-only; no i18n changes in this phase
