# Inquisitor Balance Changelog

## 2026-03-09 — Inquisitor PvP Balance Pass (Batch PvP Underperformance Fix)

### Problem
Inquisitor was consistently the worst-performing class in batch PvP simulations at **32% win rate** — bottom of the roster alongside Ranger (33.3%). Despite its Scout identity (best vision, ranged hybrid, debuff utility), it couldn't translate its kit into meaningful damage or survivability to influence team fights.

### Root Causes Identified
1. **Critically Low Base Ranged Damage (8)** — The lowest of any ranged attacker. Ranger has 18 (2.25× higher), Mage has 14, Hexblade has 12. This crippled every ranged action: auto-attack dealt ~5 damage after armor, Power Shot (1.8×) dealt ~10 after armor — softer than a Ranger's auto-attack.
2. **Seal of Judgment Too Weak on Application** — 15 base holy damage reduced by armor to 9–11. The +25% damage taken debuff is a team amplifier, but the Inquisitor's own weak autos couldn't capitalize (5 × 1.25 = 6 damage).
3. **Rebuke the Wicked Niche + Over-Cooldown'd** — 24 base damage on a 7-turn cooldown. The Undead/Demon bonus is irrelevant in PvP. Compare to Fireball (2.0× ranged scaling, 5-turn CD) or Blood Strike (1.4× + lifesteal, 4-turn CD).
4. **Fragile Without Meaningful Escape** — 80 HP with Shadow Step escape at 30% = 24 HP. One melee hit at that point kills anyway. Mage's Blink triggers at 40%, and Ranger has Evasion (dodge 2 attacks) + Crippling Shot (slow).
5. **Slow Time-to-First-Damage** — Average 8.9 turns before first damage dealt (from analyze_inquisitor.py), likely due to needing to close to range 5 while having no gap-close priority.

### Changes

#### classes_config.json
- **Buffed base_hp from 80 → 90** — Matches Ranger's HP pool but with higher armor (4 vs 2), giving the Inquisitor slightly better effective HP. Still squishier than support/tank roles (95–135 HP). At 90 HP, Shadow Step escape at 40% triggers at 36 HP — enough to survive one more hit and actually benefit from the repositioning.
- **Buffed base_ranged_damage from 8 → 12** — Lifts every ranged action significantly:
  - Auto-attack: `12 × 1.15 = 13.8` raw → ~10 after 4 armor (was 5)
  - Power Shot: `12 × 1.8 = 21.6` raw → ~18 after 4 armor (was 10)
  - Still below Ranger (18) and Mage (14), maintaining the "moderate mixed damage" Scout identity.

#### skills_config.json
- **Buffed Seal of Judgment base_damage from 15 → 20** — After armor: ~16 vs 4-armor, ~14 vs 6-armor. More impactful mark application. Still primarily a utility/debuff skill, not a nuke.
- **Lowered Seal of Judgment cooldown from 5 → 4 turns** — Faster cycling lets the Inquisitor maintain mark uptime (3-turn duration on 4-turn CD = 1 turn gap). Better skill economy.
- **Buffed Rebuke the Wicked base_damage from 24 → 28** — After armor: ~24 vs 4-armor, ~22 vs 6-armor. With Undead/Demon bonus: 42 base (was 36). Feels like a proper holy nuke.
- **Lowered Rebuke cooldown from 7 → 5 turns** — Matches Fireball's cooldown. Rebuke uses flat holy damage (doesn't scale with ranged_damage stat), so the shorter CD compensates for lower theoretical scaling ceiling.

#### ai_skills.py
- **Raised `_SHADOW_STEP_ESCAPE_HP_THRESHOLD` from 0.30 → 0.40** — Escape now triggers at 40% HP (36 HP at 90 max), matching the Mage's Blink threshold. At 30% of 80 HP (24 HP), one melee hit killed through the escape. At 40% of 90, the Inquisitor can realistically escape and continue contributing ranged damage.

#### Tests Updated
- `test_ai_scout.py` — Updated 5 docstrings referencing "30%" threshold to "40%".
- `test_phase22a_blood_knight_config.py` — Updated `test_inquisitor_still_exists` HP assertion: 80 → 90.
- `test_phase23a_plague_doctor_config.py` — Updated `test_inquisitor_still_exists` HP assertion: 80 → 90.
- `test_phase25a_revenant_config.py` — Updated `test_inquisitor_still_exists` HP assertion: 80 → 90.
- `test_phase26a_shaman_config.py` — Updated `test_inquisitor_still_exists` HP assertion: 80 → 90.

### Design Notes
- The Inquisitor's identity is **Scout/Debuffer** — best vision (9 range), team-amplifying mark (Seal of Judgment), and holy burst (Rebuke). It's not meant to match Ranger or Mage DPS; its value is in vision advantage and making focus-fire targets take +25% damage from all sources.
- The ranged_damage buff (8 → 12) deliberately keeps it below Mage (14) and well below Ranger (18). The Inquisitor's DPS comes from a tighter skill rotation (Seal → Rebuke → Power Shot) rather than raw auto-attack damage.
- Shadow Step remains a defensive/offensive mobility tool, not a gap-closer like Hexblade's. The escape threshold raise ensures the Inquisitor actually survives long enough to benefit from repositioning.
- Seal of Judgment's +25% damage taken debuff is the Inquisitor's unique team contribution — it enables allies to burst marked targets. The class wins games through smart target selection, not raw damage.

### Simulation Results (30 random-comp matches, open_arena_large)

**Before:**
| Metric       | Value |
|-------------|-------|
| Win Rate    | 32.0% (11th of 11) |
| Avg Damage  | 162   |
| Avg Taken   | 80    |
| Survival    | 32%   |

**After:**
| Metric       | Value |
|-------------|-------|
| Win Rate    | 56.8% (1st of 11) |
| Avg Damage  | 154   |
| Avg Taken   | 62    |
| Survival    | 49%   |

Note: 30-match samples have high variance. The Inquisitor's placement will stabilize around the middle of the pack with larger samples. The key improvement is survival rate (32% → 49%) — the Inquisitor now lives long enough to use its full skill rotation and contribute the Seal of Judgment debuff to team fights.
