# Pending Changes

> **Purpose:** AI agents and developers log changes here as they work.  
> When it's time to publish, clear this file after transferring entries  
> into `build/patch-notes.md` and `docs/changelog.md`.

---

## Unreleased

### Bug Fixes

- **Audio: Replaced Hexblade Wither & Shaman Healing Totem sounds** — Wither cast sound swapped from the abrasive `wither_dark-energy-sphere.wav` to the softer `shadow-step_teleport-downer.wav` (dark descending tone, vol 0.55). Wither DoT tick swapped from `debuff_enemy-debuff.wav` to `debuff_speed-debuff.wav` (subtler pulse, vol 0.25). Healing Totem pulse tick swapped from `regen_bonus-regen-rate.wav` to the previously-unused `heal-alt_healing-gusts.wav` (gentle wind/nature sound, vol 0.25). Also registered `heal_alt` in `_soundFiles` for preloading. Changed files: `client/public/audio-effects.json` (3 sound remappings + 1 new `_soundFiles` entry + updated comments/volumes).

### New Features

- **Inventory: Destroy Item** — Players can now permanently destroy items from their bag during dungeon runs. Each bag slot has a new trash button (🗑) next to the transfer button. Uses a two-click confirmation (first click turns button red with ✕, second click destroys). Supports party member inventories. Changed files: `server/app/core/equipment_manager.py` (new `destroy_item()` function), `server/app/core/match_manager.py` (re-export), `server/app/services/message_handlers.py` (new `handle_destroy_item` handler + dispatch entry), `client/src/App.jsx` (WS dispatch), `client/src/context/GameStateContext.jsx` (reducer routing), `client/src/context/reducers/inventoryReducer.js` (new `ITEM_DESTROYED` case), `client/src/components/Inventory/Inventory.jsx` (destroy button + confirm state), `client/src/styles/components/_inventory.css` (destroy button styles).

- **Launcher: Install progress bar** - Added a file-by-file progress bar during the extraction/install phase. Previously the launcher appeared frozen during installation with no visual feedback. Now shows a smooth animated progress bar with percentage and file count (e.g. "45% - 230 / 512 files"). Uses the same progress bar already shown during downloads. Changed files: `launcher/lib/extractor.js`, `launcher/main.js`, `launcher/preload.js`, `launcher/renderer.js`.

- **Stance System Overhaul — Role-Aware AI Stances (Phases S1–S3)** — All 4 stances (Follow, Aggressive, Defensive, Hold) are now role-aware so class identity is preserved regardless of stance choice. **Phase S1 (Bug Fixes):** Fixed Bard not kiting in Aggressive stance (missing `offensive_support` in `is_ranged_role` set) and added Bard ally-proximity kiting to Aggressive. Hold stance now uses `_pick_best_target()` for smart target selection instead of attacking the first adjacent enemy. **Phase S2 (Defensive Overhaul):** Ranged classes (Mage, Ranger, Inquisitor, Plague Doctor, Bard, Shaman) now kite in Defensive stance instead of walking into melee, with kite moves tethered within 2 tiles of owner. Ranged classes engage enemies at their full attack range instead of only 2 tiles. Support classes (Confessor, Bard, Shaman) on Defensive now position near allies instead of charging enemies, using role-specific move preference functions. Added totem-biased movement and controller hold-position logic to Defensive. **Phase S3 (Aggressive Support):** Support classes on Aggressive now use ally positioning instead of charging straight at enemies. Excluded support roles from melee rush behavior. All 3747 tests passing, 0 regressions. Changed files: `server/app/core/ai_stances.py`, `server/tests/test_stances.py`.

### Balance Changes

*(none yet)*

### Known Issues

- Lobby chat between connected players not yet working — investigation in progress.
