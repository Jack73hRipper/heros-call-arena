# Hexblade Balance Changelog

## 2026-03-09 — Hexblade PvP Balance Pass (Batch PvP Underperformance Fix)

### Problem
Hexblade was underperforming in batch PvP simulations. Diagnosis revealed multiple compounding issues across skill tuning, AI priority ordering, and gap-close behavior that reduced its effective damage output well below other DPS classes.

### Root Causes Identified
1. **Wasted Turn Economy (Critical)** — AI opened every fight with Ward (0 damage), then Wither (delayed damage), meaning the first 2 turns dealt near-zero burst while all other DPS classes opened with immediate damage or damage steroids.
2. **Double Strike Too Weak** — 0.6× per hit (1.2× total) was the lowest damage multiplier of any class's main damage skill, with no secondary effect. Blood Strike (1.4×), Soul Rend (1.5×), Power Shot (1.8×), and Fireball (2.0×) all outperformed it.
3. **Ward Underwhelming** — 3 charges × 8 reflect = 24 total reflect, consumed in a single turn against 5 enemies. Compare to Revenant Grave Thorns (12 reflect/hit × 4 turns = 48+) or Ranger Evasion (dodge 2 attacks entirely). Ward also does NOT reduce incoming damage.
4. **Wither Cooldown Too Long** — 6-turn cooldown yielded only 5.3 DPT (damage per turn averaged over cooldown), limiting sustained DoT pressure.
5. **Shadow Step Gap-Close Too Conservative** — Threshold of 3 tiles meant Hexblade walked slowly toward enemies at 2-3 range instead of teleporting aggressively, wasting approach turns.

### Changes

#### skills_config.json
- **Buffed Double Strike multiplier from 0.6× to 0.7× per hit** — Total damage per cast goes from 1.2× to 1.4× melee, now matching Blood Strike's multiplier. With 15 base melee damage: 10 per hit × 2 = 20 total (was 9 × 2 = 18).
- **Buffed Ward charges from 3 to 4** — Total reflect potential increases from 24 to 32 damage (4 × 8 per charge). Better survivability in 5v5 teamfights where charges are consumed quickly.
- **Lowered Wither cooldown from 6 to 5 turns** — Improves sustained DoT DPT from 5.3 to 6.4. Better uptime on armor-bypassing curse pressure.

#### ai_skills.py
- **Swapped Ward/Wither priority** — Wither is now Priority 1 (immediate DoT value on approach), Ward is Priority 2. Hexblade no longer wastes its opener on a passive shield before dealing any damage. Opening pattern is now: Wither (immediate DoT) → Ward (pre-melee shield) → engage.
- **Lowered `_SHADOW_STEP_GAPCLOSER_MIN_DISTANCE` from 3 to 2** — Shadow Step now triggers as a gap-closer when enemies are 2+ tiles away instead of 3+. More aggressive melee engagement, fewer wasted walking turns.

#### Tests Updated
- `test_double_strike_skill_definition` — Updated expected multiplier from 0.6 to 0.7.
- `test_double_strike_two_hits` — Updated expected damage from 18 to 20 (0 armor).
- `test_double_strike_armor_per_hit` — Updated expected damage from 8 to 10 (5 armor).
- `test_dispatch_double_strike` — Updated expected damage from 18 to 20.
- `test_double_strike_in_turn_resolver` — Updated expected defender HP from 82 to 80.
- `test_double_strike_with_war_cry` — Updated expected damage from 36 to 42 (with 2.0× War Cry buff).
- `test_gap_close_threshold_constant` — Updated expected value from 3 to 2.

### Design Notes
- Hexblade is intentionally a **melee auto-attacker with hybrid ranged via spells** (Wither). The `base_ranged_damage: 12` and `ranged_range: 4` in classes_config are legacy stats from early design; the class does NOT use `auto_attack_ranged` and is not intended to.
- Ward still does not reduce incoming damage — it's a punishment/reflect mechanic, not damage mitigation. The extra charge compensates for fast consumption in teamfights.
- Double Strike now matches Blood Strike's 1.4× total multiplier but trades lifesteal for a faster 3-turn cooldown (vs Blood Strike's 4 turns).

### Expected Impact
- Hexblade deals ~11% more burst damage per Double Strike cast
- Wither DoT uptime increases by ~20% (5-turn CD vs 6)
- Turn 1 now deals immediate DoT damage instead of being wasted on Ward
- More aggressive Shadow Step usage reduces wasted approach turns
- Overall PvP win rate should move closer to 50% baseline
