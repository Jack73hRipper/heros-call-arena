# Bard Balance Changelog

## 2026-03-09 — Stats, Skills & AI Tuning Pass (Batch PvP Underperformance Fix #2)

### Problem
After the AI behavior overhaul (below), Bard still sat at **37.4% win rate** across 200 randomized matches — dead last, 13 points below the 50% baseline. The AI fixes resolved wasted turns, but the underlying numbers were too weak for the class to pull its weight as a team slot.

### Root Causes Identified
1. **All 4 skills on 5-6 turn cooldowns** — Worst skill cycle in the game. After the opening buff rotation, Bard had nothing to do for 2-3 turns except auto-attack for ~5 post-armor damage.
2. **Lowest ranged damage (10)** — Tied with Shaman, but Shaman compensates with persistent totems. Bard autos were ignorable.
3. **Cacophony AI broken** — Only fired when enemies were adjacent (1 tile), but skill radius is 2. Bard's kiting behavior at distance 2 meant it retreated before Cacophony could even trigger. Direct conflict between movement AI and skill AI.
4. **Buff/debuff uptime only ~50%** — 3-turn duration / 6-turn CD meant half the fight had no Bard contribution.
5. **Dirge of Weakness underweighted** — 25% damage taken increase was weaker than Ballad's 30% damage boost.
6. **Too squishy for a support (100 HP, 3 armor)** — Zero defensive abilities combined with low effective HP meant the Bard died before delivering enough buffing value. Confessor has Heal + Shield of Faith, Shaman has totems + Soul Anchor. Bard had nothing.
7. **Ballad magnitude insufficient** — +30% team damage didn't compensate for the DPS lost by having a Bard instead of a damage class in the team slot.

### Changes

#### classes_config.json
- **Base HP: 100 → 110** — Bard needs to survive long enough to deliver value from its buff/debuff cycle. Matches Hexblade tier.
- **Base armor: 3 → 4** — One additional point of DR means ~1 less damage per hit, giving meaningful extra turns of survivability.
- **Base ranged damage: 10 → 12** — Matches Inquisitor/Plague Doctor tier. Bard autos now deal meaningful chip damage between skill casts.

#### skills_config.json
- **Ballad of Might magnitude: 1.3 → 1.4** — +40% damage (from +30%). A 5-man team buffed at 60% uptime now equates to ~96% of a DPS slot's contribution, making the Bard slot worth its cost.
- **Ballad of Might cooldown: 6 → 5** — 3/5 = 60% uptime (from 50%).
- **Dirge of Weakness cooldown: 6 → 5** — Matches Ballad cycle for tighter rotation.
- **Dirge of Weakness magnitude: 1.25 → 1.30** — +30% damage taken (from +25%).
- **Verse of Haste cooldown: 6 → 5** — The CDR class shouldn't have the longest cooldowns.
- **Cacophony base damage: 10 → 11** — Stays below Frost Nova (12) but meaningful improvement.
- **Cacophony cooldown: already 5** — No change needed.

#### ai_skills.py
- **Cacophony AI: adjacent-only → radius 2 check** — Both emergency (Priority 0) and regular (Priority 4) Cacophony now trigger when enemies are within the skill's actual radius of 2 tiles, not just when adjacent. This resolves the conflict with kiting behavior and dramatically increases Cacophony usage.

#### Tests Updated
- `test_phase21a_bard_config.py` — Updated HP (110), armor (4), ranged damage (12), skill cooldowns (5), Ballad magnitude (1.4), Dirge magnitude (1.30), Cacophony damage (11).
- `test_phase21b_bard_effects.py` — Updated Ballad magnitude (1.4), Dirge magnitude (1.30), Cacophony damage (11→89 HP).
- `test_phase21d_bard_ai.py` — Updated Cacophony docstrings (radius 2 check).

### Results
- **Before:** 37.4% win rate (200 matches, dead last)
- **After:** 47-51% win rate across 800 matches (two runs: 51.0%, 47.3%)
- Bard now sits within the healthy class cluster (46-54%) instead of 13 points below baseline
- All 125 Bard tests passing

---

## 2026-03-09 — AI Behavior Overhaul (Batch PvP Underperformance Fix)

### Problem
Bard was significantly underperforming in batch PvP win rates compared to all other classes. Root cause analysis identified several AI behavior issues unique to the Bard's `offensive_support` role that caused it to waste ~30% of its turns on passive behavior.

### Root Causes Identified
1. **Ally Centroid Trap (Critical)** — When ranged attack was on cooldown (every 3 turns), the Bard would WAIT near the ally centroid or drift toward it instead of staying in the fight. No other ranged class had this behavior.
2. **Kiting Threshold Too Defensive** — Bard retreated at distance ≤3 (same as Plague Doctor controller), keeping it too far from combat for its radius-2 Ballad/Cacophony skills.
3. **Verse of Haste Threshold Too High** — Required allies to have 2+ cooldown debt before casting, missing the most impactful early-combat CDR window.

### Changes

#### ai_behavior.py
- **Removed ally centroid WAIT block** — Deleted the `offensive_support` centroid-hold logic that made Bard WAIT or drift to ally centroid when ranged was on cooldown. Bard now falls through to normal A* pathfinding toward the enemy, keeping it engaged in combat.
- **Lowered kiting threshold from 3 to 2** — Bard now only retreats when enemies are within 2 tiles (same as Ranger/Mage) instead of 3. Keeps Bard closer to the fight for better Ballad/Cacophony/Dirge coverage.

#### ai_skills.py
- **Lowered `_VERSE_MIN_COOLDOWN_DEBT` from 2 to 1** — Verse of Haste now triggers when any ally has 1+ cooldown turn remaining. Allows Bard to use CDR more aggressively, especially in early combat when allies just used openers.

#### test_phase21d_bard_ai.py
- Updated `test_skips_verse_ally_low_cd_debt` to use ally with 0 cooldown debt (matching new threshold of 1).

### Expected Impact
- Bard no longer wastes ~6-7 turns per 20-turn fight on passive centroid behavior
- Better skill uptime from closer positioning (Ballad radius 2, Cacophony radius 2)
- More aggressive Verse usage amplifies teammate burst windows
- Overall win rate should move closer to 50% baseline
