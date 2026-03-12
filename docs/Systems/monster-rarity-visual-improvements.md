# Monster Rarity Visual Improvements

**Date:** March 4, 2026  
**Status:** Complete  
**Related:** Phase 18E (Client Visual Feedback), monster_rarity_config.json

---

## Overview

Two targeted improvements to help players immediately identify what kind of enhanced enemy they're fighting, without adding nameplate bloat.

---

## Change 1: Champion Type Name Prefix

**Problem:** All champions displayed as `"Champion Skeleton"`, `"Champion Demon"`, etc. Players couldn't tell *what kind* of champion they were fighting from the name alone — a Ghostly champion and a Berserker champion looked identical in the nameplate. The champion type info was only available in the Enemy Panel side UI.

**Solution:** Replace the generic "Champion" prefix with the actual champion type name from config.

| Before | After |
|---|---|
| Champion Skeleton | Ghostly Skeleton |
| Champion Demon | Berserker Demon |
| Champion Skeleton-2 (pack) | Resilient Skeleton-2 (pack) |

The blue name color (`#6688ff`) still signals champion tier. Now the name tells the player the threat type at a glance — matching the Diablo 2 pattern where the modifier IS the name prefix.

**Files changed:**
- `server/app/core/monster_rarity.py` — Added `get_champion_type_name()` helper that reads the `name` field from champion type config
- `server/app/core/wfc/map_exporter.py` — Dungeon spawn name generation uses `"{ChampionType} {EnemyName}"`
- `server/app/core/wave_spawner.py` — Wave spawn name generation uses `"{ChampionType} {EnemyName}"`
- `server/app/core/match_manager.py` — Champion pack member names use `"{ChampionType} {EnemyName}-{N}"`

---

## Change 2: Enemy Panel Affix Readout

**Problem:** The Enemy Panel showed affixes as a row of tiny emoji icons. Players had to hover each icon to see a tooltip with the affix name and description. During combat this was impractical — you couldn't quickly understand what you were up against.

**Solution:** Replaced the icon row with a readable affix list showing icon + name + one-line description, all visible without hovering.

**Before:**
```
🔥 ❄ ✦  (hover each for tooltip)
```

**After:**
```
🔥 Fire Enchanted — Fire damage on hit; explodes on death
🌵 Thorns — Reflects 8 melee damage
✦  Teleporter — Blinks every 3 turns
```

**Files changed:**
- `client/src/components/EnemyPanel/EnemyPanel.jsx` — Replaced `.enemy-affix-row` icon grid with `.enemy-affix-list` vertical readout
- `client/src/styles/components/_enemy-panel.css` — Added styles for `.enemy-affix-list`, `.enemy-affix-entry`, `.enemy-affix-entry-icon`, `.enemy-affix-entry-name`, `.enemy-affix-entry-desc`

---

## Test Impact

All 2454 existing tests pass. Test fixtures in `test_monster_rarity.py` and `test_monster_rarity_spawn.py` updated to use the new champion type name format.
