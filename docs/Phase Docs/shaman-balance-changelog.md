# Shaman Balance Changelog

## 2026-03-09 — Searing Totem Nerf (Batch PvP Overperformance Fix)

### Problem
Shaman was the #1 win rate class at ~62.6% in randomized 5v5 batch PvP — 10-15 points above the median. Searing Totem was identified as the single biggest contributor: it dealt armor-ignoring true damage to all enemies in a large radius, giving the Shaman massive free value every turn after placement.

### Root Causes Identified
1. **Searing Totem bypassed armor entirely** — Coded as "spirit fire" that ignored armor. Against a Crusader with 8 armor (who normally reduces damage by 8 per hit), the totem still dealt a full 6 damage/turn. Tanks had no way to mitigate it.
2. **Base damage too high at 6/turn** — Combined with armor bypass and AoE radius 2 (5×5 tile area), the totem dealt 18+ unmitigable damage per turn in clustered fights. Over 4 turns with 3 enemies, that's 72 free true damage from one skill cast.

### Changes

#### buffs_phase.py
- **Searing Totem now respects armor** — Damage is reduced by the target's armor stat (`max(1, damage - armor)`), matching how all other damage sources work. Tanks fulfill their intended role of absorbing totem damage. Minimum 1 damage guaranteed.

#### skills_config.json
- **Reduced `damage_per_turn` from 6 to 4** — Lower base combined with armor reduction brings Searing Totem in line as a supplementary damage source rather than a dominant one.
- **Updated skill description** to note armor interaction.

#### Tests Updated
- `test_phase26a_shaman_config.py` — Updated `test_searing_totem_effect` assertion (damage_per_turn 6→4).
- `test_phase26b_shaman_handlers.py` — Updated `test_searing_totem_correct_stats` assertion (damage_per_turn 6→4).
- `test_phase26c_shaman_integration.py` — Updated `_make_searing_totem` default (6→4). Updated all damage assertions across 6 tests to account for armor reduction. Renamed `test_searing_totem_ignores_armor` → `test_searing_totem_respects_armor`.

### Impact (200-match randomized batch PvP)
| Metric | Before | After |
|--------|--------|-------|
| Shaman win% | ~62.6% | ~47.7% |
| Searing dmg vs 0 armor | 6/turn | 4/turn |
| Searing dmg vs Crusader (8 armor) | 6/turn | 1/turn (min) |
| Searing dmg vs Ranger (2 armor) | 6/turn | 2/turn |

Shaman moved from dominant outlier to middle-of-the-pack — no further tuning needed for this skill.
