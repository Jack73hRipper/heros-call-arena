# PvP Batch Analysis — April 2, 2026

## Run 1: 30 Randomized Matches (open_arena_large)

**Config:** `--matches 30 --randomize --map open_arena_large --max-turns 200`

### Overall Health
- 0 draws, 0 failures — all 30 matches resolved cleanly
- Avg match length: 58 turns (median 53)
- Only 2 matches went long (103 and 163 turns) — no deadlocks
- Team A/B split: 50/50 — no spawn-side bias
- All systems exercised: damage, healing, buffs, skills, item use, deaths

### Class Performance

| Class | Win% | Games | AvgDmg | AvgHeal | K/D | DPT | AvgSurv | AvgTaken | TopHit |
|-------|------|-------|--------|---------|-----|-----|---------|----------|--------|
| Bard | 72.7% | 22 | 31 | 49 | 0.33 | 0.7 | 43.7 | 88 | 23 |
| Blood Knight | 59.1% | 22 | 348 | 127 | 3.10 | 8.3 | 42.1 | 317 | 85 |
| Revenant | 51.6% | 31 | 354 | 100 | 2.93 | 7.6 | 46.4 | 278 | 89 |
| Confessor | 50.0% | 28 | 76 | 232 | 0.32 | 1.5 | 50.3 | 227 | 34 |
| Ranger | 50.0% | 20 | 391 | 49 | 2.82 | 9.1 | 42.8 | 111 | 135 |
| Crusader | 48.3% | 29 | 134 | 194 | 0.35 | 3.0 | 44.8 | 270 | 40 |
| Plague Doctor | 48.1% | 27 | 63 | 46 | 0.21 | 1.1 | 57.0 | 113 | 32 |
| Shaman | 48.1% | 27 | 91 | 486 | 0.13 | 1.6 | 57.0 | 172 | 29 |
| Mage | 44.1% | 34 | 420 | 41 | 0.82 | 9.9 | 42.3 | 110 | 117 |
| Hexblade | 43.3% | 30 | 131 | 88 | 0.62 | 3.7 | 35.0 | 217 | 74 |
| Inquisitor | 43.3% | 30 | 332 | 53 | 0.89 | 6.6 | 50.1 | 155 | 72 |

### AI Action Distribution

| Class | Damage% | Heal% | Buff% | Move% | ItemUse% |
|-------|---------|-------|-------|-------|----------|
| Mage | 45.6% | 4.2% | 12.6% | 33.0% | 2.7% |
| Inquisitor | 44.3% | 4.0% | 17.9% | 30.5% | 2.1% |
| Shaman | 38.0% | 41.9% | 9.5% | 9.5% | 0.8% |
| Ranger | 38.8% | 4.6% | 19.4% | 32.8% | 2.9% |
| Hexblade | 37.1% | 8.2% | 23.6% | 25.0% | 4.1% |
| Revenant | 36.5% | 11.2% | 24.0% | 25.0% | 2.5% |
| Bard | 11.2% | 15.0% | 39.7% | 32.2% | 1.2% |
| Crusader | 28.8% | 13.8% | 32.8% | 21.8% | 1.8% |
| Blood Knight | 24.9% | 24.6% | 19.5% | 28.2% | 2.0% |
| Confessor | 21.9% | 18.5% | 24.5% | 30.4% | 3.1% |
| Plague Doctor | 16.8% | 3.9% | 44.7% | 30.4% | 2.8% |

### Healing vs Damage Ratios

| Class | Heal/Dmg Ratio |
|-------|---------------|
| Shaman | 536.9% |
| Confessor | 303.2% |
| Bard | 155.7% |
| Crusader | 145.4% |
| Plague Doctor | 73.5% |
| Hexblade | 67.2% |
| Blood Knight | 36.4% |
| Revenant | 28.3% |
| Inquisitor | 16.1% |
| Ranger | 12.6% |
| Mage | 9.7% |

### Long Matches (100+ turns)

| Turns | Team A | Team B | Winner |
|-------|--------|--------|--------|
| 163 | confessor, crusader, inquisitor, revenant, shaman | blood_knight, confessor, crusader, hexblade, plague_doctor | team_a |
| 103 | confessor, crusader, hexblade, inquisitor, mage | blood_knight, confessor, mage, revenant, shaman | team_b |

### Balance Flags

1. **Bard over-performing** — 72.7% win rate with only 31 avg damage. 39.7% of actions are buffs. Team-wide buff impact may be too strong.
2. **Hexblade under-performing** — 43.3% win rate, only 131 avg damage (below Crusader). Dies fastest at 35 avg survival turns. High potion dependency (4.1% item use).
3. **Plague Doctor under-delivering** — 63 avg damage, 0.21 K/D. 44.7% buff/debuff actions not translating to wins. DoTs may lack impact.
4. **Shaman healing extreme** — 486 avg healing (537% heal/dmg ratio). 41.9% of events are heals. Primary stalling risk in long matches.
5. **Mage converting poorly** — Highest raw DPS (9.9 DPT, 420 avg dmg) but 0.82 K/D and 44.1% win rate. Fragile glass cannon dying before finishing kills.

---

## Run 2: 30 Randomized Matches (open_arena_large)

**Config:** `--matches 30 --randomize --map open_arena_large --max-turns 200`

### Overall Health
- 0 draws, 0 failures — all 30 matches resolved cleanly
- Avg match length: 58 turns (median 55) — nearly identical to Run 1
- 2 matches went long (129 and 159 turns)
- Team A/B split: 73.3% / 26.7% — **notable Team A skew this run** (likely RNG comp variance)

### Class Performance

| Class | Win% | Games | AvgDmg | AvgHeal | K/D | DPT | AvgSurv | AvgTaken | TopHit |
|-------|------|-------|--------|---------|-----|-----|---------|----------|--------|
| Ranger | 60.0% | 25 | 372 | 25 | 4.40 | 8.5 | 43.9 | 84 | 94 |
| Confessor | 58.6% | 29 | 74 | 232 | 0.12 | 1.5 | 48.8 | 183 | 35 |
| Bard | 57.1% | 28 | 29 | 73 | 0.08 | 0.5 | 54.7 | 167 | 30 |
| Revenant | 54.3% | 35 | 314 | 104 | 1.74 | 7.1 | 44.2 | 266 | 132 |
| Crusader | 50.0% | 20 | 144 | 221 | 0.31 | 3.1 | 47.1 | 299 | 43 |
| Hexblade | 50.0% | 28 | 128 | 80 | 0.60 | 4.0 | 32.1 | 213 | 70 |
| Shaman | 48.0% | 25 | 66 | 365 | 0.00 | 1.3 | 49.9 | 169 | 23 |
| Inquisitor | 44.1% | 34 | 358 | 48 | 1.68 | 7.6 | 47.3 | 131 | 82 |
| Blood Knight | 43.3% | 30 | 282 | 121 | 1.29 | 7.2 | 39.0 | 340 | 123 |
| Plague Doctor | 42.9% | 21 | 58 | 50 | 0.08 | 1.3 | 44.4 | 122 | 30 |
| Mage | 40.0% | 25 | 454 | 42 | 1.00 | 9.1 | 50.0 | 104 | 172 |

### AI Action Distribution

| Class | Damage% | Heal% | Buff% | Move% | ItemUse% |
|-------|---------|-------|-------|-------|----------|
| Mage | 46.4% | 4.5% | 13.0% | 32.0% | 2.4% |
| Shaman | 38.8% | 39.7% | 9.7% | 10.7% | 0.7% |
| Ranger | 38.6% | 3.0% | 17.7% | 38.2% | 1.3% |
| Inquisitor | 37.2% | 5.0% | 18.2% | 36.3% | 2.0% |
| Hexblade | 32.9% | 10.9% | 22.7% | 27.9% | 3.6% |
| Revenant | 31.6% | 13.4% | 23.6% | 27.8% | 2.6% |
| Blood Knight | 28.4% | 22.2% | 18.8% | 27.0% | 2.4% |
| Crusader | 22.2% | 17.9% | 31.7% | 24.8% | 2.3% |
| Plague Doctor | 18.9% | 4.7% | 37.7% | 33.7% | 3.1% |
| Confessor | 18.7% | 20.6% | 23.6% | 33.8% | 2.0% |
| Bard | 9.8% | 14.7% | 41.6% | 31.2% | 1.7% |

### Healing vs Damage Ratios

| Class | Heal/Dmg Ratio |
|-------|---------------|
| Shaman | 551.8% |
| Confessor | 312.3% |
| Bard | 254.8% |
| Crusader | 153.3% |
| Plague Doctor | 86.9% |
| Hexblade | 62.3% |
| Blood Knight | 42.8% |
| Revenant | 33.2% |
| Inquisitor | 13.4% |
| Mage | 9.3% |
| Ranger | 6.8% |

### Long Matches (100+ turns)

| Turns | Team A | Team B | Winner |
|-------|--------|--------|--------|
| 159 | bard, blood_knight, inquisitor, mage, shaman | bard, blood_knight, confessor, crusader, revenant | team_b |
| 129 | blood_knight, confessor, crusader, inquisitor, revenant | bard, blood_knight, crusader, hexblade, inquisitor | team_a |

---

## Cross-Run Comparison (Run 1 vs Run 2)

### Win Rate Stability

| Class | Run 1 Win% | Run 2 Win% | Delta | Trend |
|-------|-----------|-----------|-------|-------|
| Bard | 72.7% | 57.1% | -15.6 | Normalized down but still top 3 |
| Blood Knight | 59.1% | 43.3% | -15.8 | Dropped significantly |
| Revenant | 51.6% | 54.3% | +2.7 | Stable |
| Confessor | 50.0% | 58.6% | +8.6 | Gained |
| Ranger | 50.0% | 60.0% | +10.0 | Gained — strong K/D confirms |
| Crusader | 48.3% | 50.0% | +1.7 | Stable |
| Plague Doctor | 48.1% | 42.9% | -5.2 | Slightly worse |
| Shaman | 48.1% | 48.0% | -0.1 | Rock stable |
| Mage | 44.1% | 40.0% | -4.1 | Consistently bottom |
| Hexblade | 43.3% | 50.0% | +6.7 | Improved but still low damage |
| Inquisitor | 43.3% | 44.1% | +0.8 | Stable bottom |

### Damage Consistency

| Class | Run 1 AvgDmg | Run 2 AvgDmg | Delta |
|-------|-------------|-------------|-------|
| Mage | 420 | 454 | +34 |
| Ranger | 391 | 372 | -19 |
| Revenant | 354 | 314 | -40 |
| Blood Knight | 348 | 282 | -66 |
| Inquisitor | 332 | 358 | +26 |
| Crusader | 134 | 144 | +10 |
| Hexblade | 131 | 128 | -3 |
| Shaman | 91 | 66 | -25 |
| Confessor | 76 | 74 | -2 |
| Plague Doctor | 63 | 58 | -5 |
| Bard | 31 | 29 | -2 |

### Match Length Consistency

| Metric | Run 1 | Run 2 |
|--------|-------|-------|
| Avg turns | 58 | 58 |
| Median turns | 53 | 55 |
| Min | 24 | 21 |
| Max | 163 | 159 |
| 100+ matches | 2 | 2 |
| Draws | 0 | 0 |

---

## Consolidated Findings

### Confirmed Patterns (stable across both runs)

1. **Bard is the strongest team contributor** — Top 3 win rate both runs despite dead-last damage. Buff-heavy playstyle (40% buff actions) provides massive team uplift. Worth monitoring but may be working as intended for a support class.

2. **Hexblade is the weakest DPS** — Consistently lowest survival (35 → 32 avg turns), lowest damage among non-support classes (~130), highest potion dependency (3.6-4.1% item use). Needs a damage or survivability buff.

3. **Mage has a conversion problem** — Highest raw DPS both runs (420-454 avg) but consistently bottom 3 win rate (40-44%). Glass cannon dying before kills land. May need slight HP/armor buff or AI priority targeting improvement.

4. **Plague Doctor is ineffective** — Bottom 3 both runs. ~60 avg damage, near-zero kills. 38-45% of actions are buffs/debuffs but they don't translate to wins. DoTs need more damage or debuffs need stronger effects.

5. **Shaman healing is very high but contained** — 365-486 avg healing (536-552% heal/dmg ratio). Despite this, win rate is stable at 48% — the game resolves through the healing. Not a stalling issue.

6. **Revenant and Ranger are consistently strong** — Both maintain positive K/D ratios and above-average win rates across runs. Solid class designs.

7. **Match tempo is healthy** — Avg 58 turns both runs, very few 100+ matches, zero draws. Anti-stalling systems are working.

### AI Behavior Assessment

- All classes show appropriate action distribution for their roles
- DPS classes spend 37-46% of actions dealing damage
- Healers spend 15-40% of actions healing
- Support classes prioritize buffs (38-42%)
- Item use is consistently low (0.7-4.1%) — AI uses potions as emergency only
- Movement is proportional (10-38%) — no classes spending excessive time wandering
