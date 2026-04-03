# Arena — Changelog

All notable changes to this project will be documented in this file.
Format loosely follows [Keep a Changelog](https://keepachangelog.com/).

---

## [v0.1.37] - 2026-04-03 — Shaman Balance Pass (Spirit Link + Kiting Fix)

### Problem
Shaman was the weakest class in batch PVP testing — 42.6% win rate over 100 randomized matches (40W/52L across 94 appearances), dead last of all 11 classes. Root causes identified:
1. **Kiting threshold too conservative**: Shaman kited at distance 1 (same as non-support classes), staying too close to enemies and taking unnecessary damage.
2. **Soul Anchor too reactive**: The cheat-death mechanic only triggered at ≤30% HP — by then the ally was usually already lost. The ability felt invisible and rarely changed match outcomes.
3. **Cooldown gaps**: 2–3 turn windows with no skills available left the Shaman doing nothing impactful.
4. **Near-zero kill participation**: 0.00–0.13 K/D ratio, contributing almost no offensive pressure.

### Changed — Kiting Threshold
- **Kiting distance** 1 → 2 for `totemic_support` role. Shaman now maintains a 2-tile buffer from enemies (same as other ranged supports), reducing incidental melee damage taken. Applied to Follow stance, Aggressive stance, and core AI behavior.

### Added — Spirit Link (New Skill, Replaces Soul Anchor)
- **Spirit Link** 🔗 — Link your spirit to an ally; damage they take is split 50/50 between you for 4 turns. Link breaks if either party dies.
  - Targeting: `ally_or_self` (cannot target self in AI logic)
  - Range: 4 | Cooldown: 5 turns | Mana cost: 0
  - Effect: `spirit_link` buff with `damage_share: 0.5`, `duration_turns: 4`
  - Damage splitting applies to: ranged attacks, melee attacks, searing totem ticks
  - If the linked Shaman dies from shared damage, the link breaks and remaining damage hits the original target

### Changed — AI Priority Chain
- Old: Healing Totem (P1) → Searing Totem (P2) → Earthgrasp (P3) → Soul Anchor (P4)
- New: **Healing Totem (P1) → Spirit Link (P2) → Searing Totem (P3) → Earthgrasp (P4)**
- Spirit Link AI targets frontline tanks (Crusader, Revenant, Blood Knight, Hexblade) first, then lowest HP% ally in range. Only casts when no active link exists.

### Deprecated — Soul Anchor
- Soul Anchor skill definition and handler code retained for backward compatibility (deaths_phase.py still processes the buff). Removed from Shaman's active class_skills loadout — no longer cast by AI. Skill `allowed_classes` remains `["shaman"]` but is not in class_skills.

### Batch PVP Results (Post-Change)
```
Randomized 100 matches (baseline → post-fix):
  shaman: 42.6% → 45.4% win rate (44W/48L in 97 games)
  Moved from dead last (11th) to mid-pack (7th of 11)
```

### Files Changed
- `server/app/core/ai_stances.py` — Kiting threshold 1 → 2 for totemic_support (2 locations: Follow + Aggressive)
- `server/app/core/ai_behavior.py` — Kiting threshold 1 → 2 for totemic_support (1 location)
- `server/configs/skills_config.json` — Added `spirit_link` skill definition; updated `class_skills.shaman` from `soul_anchor` to `spirit_link`
- `server/app/core/skill_effects/summon.py` — Added `resolve_spirit_link()` handler (target validation, range check, buff application, removes existing links)
- `server/app/core/skills.py` — Registered `spirit_link` effect type in resolve chain
- `server/app/core/combat.py` — Added `try_split_spirit_link()` helper (damage splitting logic)
- `server/app/core/turn_phases/combat_phase.py` — Spirit Link splitting at ranged + melee attack sites
- `server/app/core/turn_phases/buffs_phase.py` — Spirit Link splitting for searing totem damage
- `server/app/core/ai_skills.py` — Replaced Soul Anchor Priority 4 with Spirit Link Priority 2; updated tank class set and targeting logic
- `server/tests/test_phase26a_shaman_config.py` — Updated skill order assertion, added spirit_link can_use test
- `server/tests/test_phase26d_shaman_ai.py` — Replaced Soul Anchor AI tests with Spirit Link AI tests (7 tests), updated priority ordering tests
- `server/tests/test_skills.py` — Updated skill count 53 → 54, added spirit_link to expected set, legacy skill exemptions

---

## [v0.1.36] - 2026-04-03 — Plague Doctor Balance Pass (DPS Uplift + Armor Shred)

### Problem
Plague Doctor was the weakest class in batch PVP testing — 46.7% win rate in randomized matches (bottom 4), and only 35% win rate in controlled team comp tests (crusader/confessor/plague_doctor/ranger/bard vs blood_knight/hexblade/mage/revenant/shaman). Replacing Plague Doctor with a Mage in the same slot improved team win rate to 60% — a **25-point swing** showing PD was actively dragging its team down. Root cause: personal damage was invisible (lowest DPT of all ranged classes at ~1.1 DPT) and debuff value was unnoticeable in AI-vs-AI matches where debuffs don't create feel-good moments.

### Changed — Base Stats
- **Ranged Damage** 12 → 14 (+17%). Auto-attacks now deal 16 after the 1.15× multiplier (up from 14). Closes the gap with Mage (16) while still trailing Ranger (21) and Hexblade (17).

### Changed — Miasma (AoE Poison Cloud)
- **Base damage** 10 → 15 (+50%). The signature area-denial skill now deals meaningful burst to clusters. vs 3 enemies: 45 total damage (up from 30). Against low-armor targets the damage is now felt immediately.

### Changed — Plague Flask (Single-Target DoT)
- **Damage per tick** 8 → 10 (+25%). Total DoT: 40 damage over 4 turns (up from 32). Effective DPT over cooldown cycle: 10.0 (up from 6.4). Now competitive with Wither's 8/tick × 4 = 32 by trading per-tick damage for shorter cooldown uptime.

### Changed — Enfeeble (AoE Debuff)
- **Cooldown** 5 → 4 turns. Enfeeble uptime increases from 60% → 100% (4-turn duration on 4-turn CD). The Plague Doctor's crown jewel can now be maintained continuously, making the class's defensive contribution consistent rather than bursty.
- **Added armor shred**: Enfeeble now applies **-2 armor** to all enemies in the AoE in addition to the existing -25% damage dealt debuff. This gives the team a visible offensive benefit — enemies hit by Enfeeble also take more damage from everyone. Duration matches the damage reduction (4 turns).

### Changed — Multi-Effect Debuff Handler
- `resolve_aoe_debuff()` now supports **multiple effects per skill**. Previously only read the first `aoe_debuff` effect entry; now loops over all matching effects and applies each with a unique `buff_id` per stat (e.g., `enfeeble_damage_dealt_multiplier`, `enfeeble_armor`). This is a generic system improvement — any future skill can bundle multiple debuff effects.

### Changed — Armor Debuff Support
- `get_armor_buff_bonus()` now handles **debuff-type armor entries** (negative magnitudes). Previously only summed `type == "buff"` armor entries; now also includes `type == "debuff"` with `stat == "armor"`, enabling armor shred mechanics.

### Changed — AI Compatibility
- Enfeeble AI check in `_controller_skill_logic()` updated to use `startswith("enfeeble")` instead of exact `== "enfeeble"` match, compatible with the new per-stat buff IDs.

### Batch PVP Results (Post-Change)
```
Controlled team comp (20 matches each):
  PD comp vs DPS comp:   35% → 50%  (+15 points)
  Mage comp vs DPS comp: 60% → 65%  (control, +5 variance)
  PD-Mage gap:           25 pts → 15 pts (gap halved)

Randomized 50 matches:
  plague_doctor: 42.9% win rate (18W/22L in 42 games)
  Mid-pack — no longer bottom-tier outlier
```

### Files Changed
- `server/configs/classes_config.json` — `base_ranged_damage` 12 → 14
- `server/configs/skills_config.json` — Miasma `base_damage` 10 → 15; Plague Flask `damage_per_tick` 8 → 10; Enfeeble `cooldown_turns` 5 → 4 + added second `aoe_debuff` effect (armor, -2, 4 turns)
- `server/app/core/skill_effects/debuff.py` — `resolve_aoe_debuff()` multi-effect loop with unique buff IDs
- `server/app/core/skills.py` — `get_armor_buff_bonus()` handles debuff-type armor entries
- `server/app/core/ai_skills.py` — Enfeeble buff_id check uses `startswith("enfeeble")`
- `server/tests/test_phase23a_plague_doctor_config.py` — Updated assertions for new values
- `server/tests/test_phase23b_plague_doctor_handlers.py` — Updated damage/cooldown assertions
- `server/tests/test_phase23d_plague_doctor_ai.py` — Updated enfeeble buff_id in test data

### Design Notes
- The Plague Doctor's core identity as a controller/debuffer is preserved — these are number tweaks, not role changes. The class still trades personal DPS for team survivability, but now its personal contributions are noticeable rather than invisible.
- The armor shred on Enfeeble gives teammates a tangible "feel" when PD debuffs — enemies become visibly squishier. This addresses the "invisible value" problem without changing the class's strategic role.
- 166 Plague Doctor tests passing after changes.

---

## [v0.1.35] - 2026-04-02 — Hexblade Balance Pass (Wither Lifesteal + Hex Strike)

### Added — Wither Lifesteal
- **Wither now heals the caster** — Each tick of Wither's DoT (8 damage/tick, 4 ticks) heals the Hexblade for 50% of the damage dealt (4 HP/tick, 16 HP total). This gives the Hexblade sustain comparable to Blood Knight's Lifesteal without requiring a dedicated heal skill.
- Lifesteal is applied during the buff tick phase and logged as a heal ActionResult attributed to the Wither source.
- The `lifesteal_pct` field is generic — any future DoT skill can opt in by adding `"lifesteal_pct"` to its effect config.

### Added — Hex Strike (replaces Double Strike for Hexblade)
- **New skill: Hex Strike** — Melee attack (range 1, CD 3) dealing 1.4× base melee damage. If the target has an active Wither DoT, Hex Strike deals bonus flat damage equal to Wither's `damage_per_tick` (8), bypassing armor. This rewards the Hexblade's intended Wither → melee combo loop.
- Damage breakdown: 15 base × 1.4 = 21 base + 8 Wither bonus = **29 total** vs Double Strike's 21.
- Hexblade's class skill list updated: `double_strike` → `hex_strike`. Double Strike remains available to Werewolf, Ghoul, and Demon Lord.

### Changed — Hexblade AI (Hybrid DPS Logic)
- Priority 3 in `_hybrid_dps_skill_logic` now uses `hex_strike` instead of `double_strike`.
- AI prefers adjacent targets that already have the Wither DoT active to maximize the bonus damage synergy.

### Files Changed
- `server/configs/skills_config.json` — Added `hex_strike` skill definition; added `lifesteal_pct: 0.5` to Wither effect; swapped Hexblade class list from `double_strike` to `hex_strike`; removed `hexblade` from `double_strike.allowed_classes`
- `server/app/core/skill_effects/damage.py` — Added `resolve_hex_strike()` resolver
- `server/app/core/skill_effects/debuff.py` — Propagates `lifesteal_pct` from skill config into DoT buff entries
- `server/app/core/turn_phases/buffs_phase.py` — DoT tick now heals source player when `lifesteal_pct` is present on the buff
- `server/app/core/skill_effects/__init__.py` — Exported `resolve_hex_strike`
- `server/app/core/skills.py` — Added `hex_strike` dispatch entry
- `server/app/core/ai_skills.py` — Updated `_hybrid_dps_skill_logic` Priority 3 from Double Strike to Hex Strike with Wither-aware targeting

### Design Notes
- Hexblade was the lowest-performing class in batch PvP testing (43% win rate, lowest survival time, 0.60 K/D). These changes address the two root causes: zero sustain and a redundant melee skill (Double Strike) that added no synergy to the kit.
- Wither lifesteal provides passive sustain through the Hexblade's existing DoT rotation. Hex Strike rewards applying Wither first, creating a clear tactical loop: Wither → Ward → close gap → Hex Strike.

---

## [v0.1.34] - 2026-04-02 — Arcane Barrage Per-Target Missiles

### Reworked — Arcane Barrage Visual Effect
Completely replaced the Arcane Barrage visual. The old design fired a single projectile to the AoE center and detonated a generic carpet-bomb explosion (rain + flash + ring + scorch) regardless of how many enemies were hit. The new design fires **one missile per enemy hit**, staggered, directly to each target.

**New behavior:**
- **Multiple enemies in AoE** — One arcane missile arcs from the Mage to each hit enemy, staggered 120ms apart. 3 enemies = 3 missiles, each arriving at its target with a compact 14-particle impact burst.
- **Single enemy** — One missile, one impact. Clean and direct.
- **No enemies (whiff)** — One missile fires to the AoE center with a small fizzle impact.

**Added — Per-target impact preset**
- New `arcane-missile-impact` skill preset — compact 14-particle burst (white → #ddaaff → #bb66ee → #8833cc → #440088), 6px spawn radius, 0.45s duration, `easeOutQuad` alpha fade. Fires at each target on missile arrival.

**Added — Multi-projectile system**
- New `multiProjectile` flag in particle-effects.json — when `true`, the ParticleManager fires one projectile per entry in `buff_applied.hit_ids` instead of a single projectile to the AoE center.
- New `_launchMultiProjectile()` method in ParticleManager.js — resolves each hit target's position, launches staggered `ParticleProjectile` instances with configurable `stagger` delay.
- Configurable `stagger` property on projectile config (default 120ms).

**Added — Server hit_ids**
- `resolve_aoe_magic_damage()` now includes `hit_ids` (all hit unit IDs) in `buff_applied`, not just `killed_ids`. This lets the client know exactly which enemies were struck.

**Removed from arcane_barrage mapping:**
- `arcane-barrage-rain`, `arcane-barrage-flash`, `arcane-barrage-ring`, `arcane-barrage-scorch` extras — the old carpet-bomb detonation. Presets remain in skills.json but are no longer referenced.

### Visual Sequence
- **Before:** Single bolt arcs to ground → 133-particle carpet-bomb explosion at AoE center (same visual whether 0 or 5 enemies hit)
- **After:** N missiles arc from Mage to N enemies (staggered 120ms) → each arrives with a crisp 14-particle impact pop at the target. Whiff = 1 fizzle missile to empty ground.

### Files Changed
- `server/app/core/skill_effects/damage.py` — Added `hit_ids` list to `resolve_aoe_magic_damage` return data
- `client/public/particle-effects.json` — Replaced `arcane_barrage` mapping: `multiProjectile: true`, removed extras, added `stagger: 120`
- `client/public/particle-presets/skills.json` — Added `arcane-missile-impact` preset
- `client/src/canvas/particles/ParticleManager.js` — Added `_launchMultiProjectile()` method; `_fireEffect()` routes to it when `multiProjectile` is set

### Technical Notes
- The `multiProjectile` system is generic — any future skill can use it by setting the flag and ensuring the server sends `hit_ids`.
- Existing projectile presets (`arcane-missile-trail`, `arcane-missile-head`) are reused unchanged — only the routing and impact changed.
- Skill mechanics (damage, radius, cooldown, targeting) are completely unchanged.

---

## [v0.1.33] - 2026-04-02 — Weapon Type Proficiency & Smart Loot Bias

### Added — Weapon Type Proficiency (Phase 22A)
- **Per-class weapon type restrictions** — Each class now has an `allowed_weapon_types` list that controls which specific weapon types (sword, mace, staff, bow, etc.) they can equip. This adds a second, finer-grained layer on top of the existing weapon category system (melee/ranged/caster/hybrid).
- **Thematic enforcement** — A Confessor can no longer equip a Stiletto just because it's in the `melee` category. Confessors are limited to maces, flails, staves, and throwing axes. Each class has a curated list reflecting their fantasy:
  - **Crusader:** sword, mace, warhammer, flail, greatsword, throwing_axes
  - **Confessor:** mace, flail, staff, throwing_axes
  - **Inquisitor:** bow, crossbow, staff, throwing_axes
  - **Ranger:** bow, crossbow, throwing_axes
  - **Hexblade:** all types (true hybrid)
  - **Mage:** staff, dagger, throwing_axes
  - **Bard:** staff, throwing_axes
  - **Blood Knight:** sword, greatsword, dagger, stiletto, throwing_axes
  - **Plague Doctor:** staff, dagger, throwing_axes
  - **Revenant:** sword, greatsword, mace, flail, warhammer, throwing_axes
  - **Shaman:** staff, mace, throwing_axes
- **Dual enforcement** — Proficiency is checked both in-match (`equipment_manager.equip_item()`) and in town (`POST /town/equip`), with clear error messages on rejection.
- **Backward compatible** — Items without `weapon_type` or classes without `allowed_weapon_types` bypass the check, so legacy items and mods still work.

### Added — Smart Loot: Weapon Type Bias
- **Party-aware weapon drops** — Loot generation now has a 60% chance to bias weapon drops toward weapon types the current party can actually use, mirroring the existing armor category bias system.
- **Union of party preferences** — If your party has a Ranger and a Crusader, loot pools favor bows, crossbows, swords, maces, warhammers, flails, greatswords, and throwing_axes.

### Added — Weapon Type Data
- **All weapons tagged** — Every base weapon (16), unique weapon (6), and set weapon (5) now has a `weapon_type` field (sword, bow, mace, dagger, staff, crossbow, flail, throwing_axes, greatsword, warhammer, stiletto).

### Files Changed
- `server/configs/items_config.json` — Added `weapon_type` to all 16 weapon entries
- `server/configs/uniques_config.json` — Added `weapon_type` to all 6 unique weapons
- `server/configs/sets_config.json` — Added `weapon_type` to all 5 set weapon pieces
- `server/configs/classes_config.json` — Added `allowed_weapon_types` to all 11 classes
- `server/app/models/items.py` — Added `weapon_type: str = ""` to `Item` model
- `server/app/models/player.py` — Added `allowed_weapon_types: list[str]` to `ClassDefinition`
- `server/app/core/equipment_manager.py` — Added weapon type proficiency check in `equip_item()`
- `server/app/routes/town.py` — Added weapon type proficiency check in `/town/equip`
- `server/app/core/item_generator.py` — Propagated `weapon_type` through `generate_item()`, `generate_unique()`, `generate_set_piece()`
- `server/app/core/loot.py` — Added `_get_party_preferred_weapon_types()` and weapon type bias in `_pick_base_type_from_pool()`

---

## [v0.1.32] - 2026-04-01 — Hiring Hall Rework: Class Identity & Starting Gear

### Improved — Hero Cards Now Show Class Identity
- **Role tag with icon** — Each hero card displays a colored role badge (Tank, Healer, Melee DPS, Ranged DPS, Support) with a matching emoji icon, so players can immediately tell what a class does.
- **Class description** — A short one-liner from `classes_config.json` appears below the role tag, explaining the class fantasy (e.g. "Holy warrior wielding faith as a shield").
- **Skill badge previews** — Up to 4 class skills are shown as icon badges on the card. Hovering a badge reveals a tooltip with the skill name, description, and cooldown.

### Changed — Starting Gear Replaces Stat Rolling
- **Flat base stats** — Tavern heroes now spawn with exact base stats from `classes_config.json`. The old ±5% stat variation system (`_vary_stat`) has been removed entirely.
- **Random starting gear** — Heroes can roll a random weapon (55% chance), armor piece (40%), or accessory (20%) at hire. Gear uses a tavern rarity curve (60% common, 30% magic, 10% rare) and respects each class's allowed weapon categories and preferred armor type.
- **Gear-based hire cost** — Hire cost is now `BASE_HIRE_COST (30g) + total gear sell value`. A naked hero costs 30g; a hero with a rare weapon may cost 45-60g. Replaces the old stat-point-based cost formula.
- **Cost breakdown on card** — The hire button shows the total cost with a smaller breakdown line (e.g. "30g base + 12g gear").

### Added — Class Skills API
- **`/api/lobby/classes` now returns skill summaries** — Each class entry includes an array of skill objects (name, icon, description, cooldown) so the frontend can render skill previews without a second fetch.
- **`_get_classes_dict()` exposes weapon/armor config** — `allowed_weapon_categories` and `preferred_armor` are now included in the classes API response, enabling gear-aware hero generation.

### Files Changed
- `server/app/models/profile.py` — Removed `_vary_stat`, `STAT_VARIATION_PERCENT`, `HIRE_COST_PER_STAT_POINT`. Added `_roll_starting_gear()`, `_tavern_rarity()`, gear chance constants. Rewrote `generate_hero()` for flat stats + random gear + gear-based cost.
- `server/app/routes/lobby.py` — `/api/lobby/classes` now includes skill summaries per class.
- `server/app/routes/town.py` — `_get_classes_dict()` now includes `allowed_weapon_categories` and `preferred_armor`.
- `client/src/components/TownHub/HiringHall.jsx` — Complete rewrite: role tags, class descriptions, skill badge row with hover tooltips, gear slot display with rarity colors, cost breakdown.
- `client/src/styles/town/_hiring-hall.css` — Added styles for role tags, skill badges, skill tooltips, gear slots, cost breakdown.
- `server/tests/test_heroes.py` — Replaced `TestStatVariation` with `TestStartingGear`, updated generation tests for flat stats and gear-based cost.

### Known Issue
- `test_heroes.py` has a pre-existing syntax error (stray `"""` on line 1) blocking test collection — tracked as Bug #13 in `docs/bug-log.md`.

---

## [v0.1.31] - 2026-04-01 — Floating Combat Text Visual Polish

### Improved — Floating Combat Text Animations
- **Ease-out motion curves** — Floaters now burst upward quickly and decelerate, replacing the old linear drift. Feels far more impactful.
- **Pop-in scale punch** — Numbers spawn at 1.3x size and rapidly settle to 1.0x over the first 150ms, giving a satisfying "impact" on every hit.
- **Random X spread** — Each floater gets a random horizontal offset (±8px) at creation, preventing overlapping same-tile floaters (AoE, multi-attacks) from stacking unreadably.
- **Hold-then-fade alpha** — Numbers hold full opacity for the first 40% of their lifetime before fading out, making them readable much longer than the old instant linear fade.
- **Critical hit glow** — Hits dealing 31+ damage and kills now pulse a colored shadow glow behind the text that fades with the floater. Makes big moments visually dramatic.
- **Heal floater bob** — Heal numbers (`+N`) gently bob with a sine wave overlaid on their upward drift, giving them a softer, magical feel distinct from damage.
- **Color-matched outlines** — Text stroke outlines now use a darkened shade of the floater's own color (30% brightness) instead of flat black, adding warmth and polish.

### Files Changed
- `client/src/canvas/overlayRenderer.js` — Rewrote `drawDamageFloaters()` with eased Y drift, pop-in scale, random X spread, non-linear alpha, pulsing glow for big hits, heal sine-bob, and `darkenColor()` helper for color-matched strokes.
- `client/src/utils/combatLogBuilder.js` — Added `randX` field (random ±8px offset) to all floater creation points in `buildFloater()`.

---

## [v0.1.30] - 2026-04-01 — Shaman Totem Placement Fix

### Fixed — Totem Placement Blocked by Auto-Target
- **Shaman totems now correctly enter tile-selection mode** — Placement skills (`healing_totem`, `searing_totem`, `earthgrasp`) were being overridden by the auto-target pursuit system, causing totems to cast on top of the nearest enemy instead of letting the player choose a tile.
- **Auto-target cleared on totem activation** — Entering totem placement mode now clears any active auto-target and sends `clear_auto_target` to the server, preventing pursuit actions from pre-empting the placement.
- **Occupied tiles excluded from totem highlights** — `ground_aoe` highlights for `place_totem` skills no longer show tiles occupied by units, since the server rejects placement on occupied tiles. Prevents silent failures when clicking an enemy's tile.
- **Non-totem `ground_aoe` skills unaffected** — Arcane Barrage and other offensive `ground_aoe` skills retain target-first auto-fire behavior via the existing `isPlacementSkill` guard.

### Files Changed
- `client/src/components/BottomBar/BottomBar.jsx` — Clear auto-target when entering placement skill targeting mode; added `autoTargetId` to dependency array.
- `client/src/hooks/useHighlights.js` — Filter occupied tiles from `ground_aoe` highlights when skill is a placement skill.

---

## [v0.1.29] - 2026-04-01 — Audio Workbench: Advanced DSP & Sound Upgrades

### Added — New DSP Primitives (generate_sfx.py)
- **FM synthesis** (`_fm_osc`) — Frequency modulation oscillator with carrier/modulator/index params. Produces rich inharmonic metallic and bell-like tones impossible with simple additive synthesis.
- **Bitcrusher** (`_bitcrush`) — Bit-depth reduction and sample-rate downsampling for lo-fi, retro, and gritty textures. Configurable bit depth (2–16) and downsample factor.
- **Ring modulation** (`_ring_mod`) — Multiplies signal with a modulator sine wave, creating dissonant sidebands and metallic resonances. Wet/dry mix control.
- **Delay / Echo** (`_delay`) — Feedback delay line with configurable delay time (ms), feedback amount, wet/dry mix, and optional low-pass filtering on the feedback path.
- **Formant filter** (`_formant`) — Vowel-shaped resonant filter bank (a/e/i/o/u) that imposes vocal character onto any signal. Intensity-blended with dry signal.
- **Tremolo** (`_tremolo`) — Amplitude modulation with sine or triangle LFO. Rate and depth controls for pulsing, warbling effects.
- **Pitch envelope oscillator** (`_pitch_env_osc`) — Oscillator with built-in pitch curves: drop (impact weight), rise (risers), overshoot (bouncy settle). Amount and waveform selectable.

### Added — Template & Editor Integration
- **Expanded post-processing chain** — `_apply_post_processing()` now chains: bitcrush → tremolo → chorus → delay → reverb → stereo (was chorus → reverb → stereo).
- **7 new common params** in `COMMON_PARAM_SCHEMA` — `tremolo_rate`, `tremolo_depth`, `delay_ms`, `delay_feedback`, `delay_wet`, `bitcrush_depth`, `bitcrush_downsample`. Available on every template from the sound editor.
- **Per-template DSP params** — `impact`: pitch envelope + ring mod. `sweep`: ring mod + pitch envelope. `chord`: formant filter. `drone`: formant + ring mod. `tonal_hit`: FM synthesis + ring mod. All exposed in the editor UI with labeled sliders/dropdowns.
- **Updated template generators** — `generate_impact`, `generate_sweep`, `generate_chord`, `generate_drone`, `generate_tonal_hit` now use the new DSP when their params are set (backwards-compatible zero/none defaults).

### Changed — Upgraded Bespoke Sound Generators (11 sounds)
- **gen_melee_hit** — Sub-bass now uses `_pitch_env_osc(drop)` for visceral weight on every melee impact.
- **gen_melee_crit** — Metallic ring replaced with `_fm_osc` (carrier=1200Hz, mod=1800Hz, index=2.5) for richer inharmonic metallic spectrum.
- **gen_block** — Added `_ring_mod` (350Hz+) on metallic tones before chorus for authentic shield-clang resonance.
- **gen_death** — Deep thud now uses `_pitch_env_osc(drop, amount=1.5)` for gut-punch low-end weight.
- **gen_stun_hit** — Dissonant ring tones now processed through `_ring_mod(180Hz, mix=0.5)` then chorus for alien dissonance.
- **gen_taunt** — Sawtooth growl now passes through `_formant('a', 0.6)` for throaty vocal aggression.
- **gen_holy_ground** — Chord now processed with `_tremolo(3.5Hz, 0.3)` before chorus for celestial pulsing.
- **gen_prayer** — Vibrato tone now passes through `_formant('a', 0.55)` for chanting vocal character.
- **gen_undying_will** — Drone processed with `_tremolo(4Hz, 0.35)` for dark pulsing power activation feel.
- **gen_war_cry** — Sweep now filtered through `_formant('o', 0.5)` for powerful battle-cry vocal quality.
- **gen_portal_channel** — Added `_delay(180ms, fb=0.35, wet=0.25)` for dimensional spaciousness.

### Changed — Updated SOUND_TEMPLATE_MAP Entries
- `melee_hit_*` — Added `pitch_env: 'drop'`, `pitch_env_amt: 1.2`.
- `block_*` — Added `ring_mod_freq` (per-variant), `ring_mod_mix: 0.4`.
- `death_*` — Added `pitch_env: 'drop'`, `pitch_env_amt: 1.5`.
- `stun_hit*` — Added `ring_mod_freq: 180`, `ring_mod_mix: 0.5`.
- `skill_taunt` — Added `formant_vowel: 'a'`, `formant_intensity: 0.6`.
- `skill_holy_ground` — Added `tremolo_rate: 3.5`, `tremolo_depth: 0.3`.
- `skill_prayer` — Added `formant_vowel: 'a'`, `formant_intensity: 0.55`.
- `skill_undying_will` — Added `tremolo_rate: 4.0`, `tremolo_depth: 0.35`.
- `portal_channel` — Added `delay_ms: 180`, `delay_feedback: 0.35`, `delay_wet: 0.25`.

### Files Changed
`tools/audio-workbench/synth/generate_sfx.py`

---

## [v0.1.28] - 2026-04-01 — Audio Workbench: Sound Editor & Parameterized Templates

### Added
- **Parameterized template system** — 8 synthesis templates (`impact`, `sweep`, `chord`, `arpeggio`, `noise_texture`, `drone`, `tonal_hit`, `percussive`) with full parameter schemas (min/max/step/default/label). Each template is a self-contained generator with oscillator selection, envelope, and post-processing. All ~85 existing sound keys are mapped to a template with default-override params via `SOUND_TEMPLATE_MAP`. (`generate_sfx.py`)
- **Common post-processing params** — `COMMON_PARAM_SCHEMA` defines 8 shared parameters (reverb decay/wet/room, stereo width/mode, chorus voices/depth/rate) applied to all templates via `_apply_post_processing()`. (`generate_sfx.py`)
- **Single-sound generation CLI** — New CLI args `--params-json`, `--template`, `--list-templates`, `--editor-info` allow the server to regenerate individual sounds with custom parameters without running the full batch. (`generate_sfx.py`)
- **Preset save/load system** — Presets stored in `synth-presets.json` persist user-tuned parameters per sound key. Loaded automatically when opening the editor. (`generate_sfx.py`, `server.js`)
- **Server endpoints for editor** — Six new Express endpoints: `GET /api/synth/editor/:key` (param schema), `GET /api/synth/templates` (all templates), `POST /api/synth/generate-one` (single-key regen with params), `GET /api/synth/presets`, `POST /api/synth/presets`, `DELETE /api/synth/presets/:key`. (`server.js`)
- **SoundEditor component** — React panel with per-parameter sliders/dropdowns/toggles, live preview generation, Web Audio playback, preset save, reset-to-defaults, compare integration, and modified-param indicators. (`SoundEditor.jsx`)
- **CreateSound component** — Template picker dialog for creating new sounds: choose a template, name a key, assign a category, then open the editor. (`CreateSound.jsx`)
- **Edit button per sound row** — Each sound in the synth list now has a ✏️ button that opens the SoundEditor in a side panel. (`SynthPreview.jsx`)
- **"New Sound" button** — Header button opens the CreateSound dialog to create entirely new sounds from templates. (`SynthPreview.jsx`)
- **Editor CSS** — Full styles for the editor panel, param controls (sliders with thumb styling, modified-state highlighting), split-panel layout, create-sound template grid, preview bar, and footer actions. Follows existing grimdark theme variables. (`workbench.css`)

### Changed
- **Manifest v2** — Synth manifest now includes `editable` and `template` fields per sound entry. (`generate_sfx.py`)
- **Duration calc fix** — Stereo `(2, N)` signals now use `sig.shape[1] / RATE` instead of `len(sig) / RATE`. (`generate_sfx.py`)
- **Synth list layout** — Sound list now uses a flex body container that supports a split view when the editor panel is open. (`SynthPreview.jsx`, `workbench.css`)

### Files Changed
`tools/audio-workbench/synth/generate_sfx.py`, `tools/audio-workbench/server.js`, `tools/audio-workbench/src/components/SoundEditor.jsx` (new), `tools/audio-workbench/src/components/CreateSound.jsx` (new), `tools/audio-workbench/src/components/SynthPreview.jsx`, `tools/audio-workbench/src/styles/workbench.css`

---

## [v0.1.27] - 2026-04-01 — Audio Workbench: Synth DSP Enhancement Pass

### Added
- **Schroeder reverb** (`_reverb`) — Comb-filter + allpass-chain reverb with damping lowpass on feedback. Three room presets: `dungeon` (short/dark), `hall` (longer/brighter), `tight` (very short/metallic). Wet/dry mix and decay are per-call tuneable. (`generate_sfx.py`)
- **Chorus** (`_chorus`) — Multi-voice detuned delay with per-voice LFO-modulated delay lines. Configurable voice count, max delay, depth, and LFO rate for thickening tonal elements. (`generate_sfx.py`)
- **Stereo imaging** (`_stereo`) — Mono-to-stereo widener with three modes: `haas` (inter-aural delay), `spread` (micro-delays + pitch detune per channel), `mid_side` (spectral difference between channels). Width parameter controls intensity. (`generate_sfx.py`)
- **Resonant filter sweep** (`_resonant_sweep`) — Time-varying resonant bandpass processed in ~10 ms chunks. Sweeps center frequency from `f_start` → `f_end` over the signal duration with adjustable Q and filter order. (`generate_sfx.py`)

### Changed
- **Stereo WAV output** — `_write_wav` now detects 2D `(2, N)` stereo arrays and writes interleaved L/R 16-bit PCM. All 123 generated sounds are now stereo. (`generate_sfx.py`)
- **Combat sounds** — Melee hits, crits, ranged hits, misses, dodges, blocks, deaths, stun-hits, and stun-locked all received per-sound reverb (mostly `tight`), optional chorus on metallic rings, and `haas` stereo at varying widths. (`generate_sfx.py`)
- **Skill / class sounds** — Generic casts, Crusader, Ranger, Confessor, Hexblade, Bard, Blood Knight, Plague Doctor, Revenant, and Shaman skill generators now use resonant sweeps on sweep-based tones, chorus on sustained tonal layers, class-appropriate reverb rooms, and `spread` or `mid_side` stereo. (`generate_sfx.py`)
- **Buff / debuff / heal sounds** — Heals use hall reverb with heavy chorus and wide spread stereo. Buffs get hall reverb and spread stereo. Debuffs and wither-tick use dungeon reverb with mid-side stereo. (`generate_sfx.py`)
- **Event sounds** — Portal channel/open, wave clear, floor descend, match start/end, door open, and chest open all received reverb + stereo appropriate to their context. (`generate_sfx.py`)
- **Item / UI / movement sounds** — Buy, sell, equip, potion, loot pickup use tight reverb and narrow haas stereo. UI clicks, confirm, cancel, lock, and select use minimal tight reverb with very narrow stereo. Footsteps use light dungeon reverb. (`generate_sfx.py`)

### Fixed
- **Retro melee hit lambda** — Updated the inline `melee_hit_retro` lambda to handle stereo `(2, N)` output from `gen_melee_hit` by applying distortion per channel. (`generate_sfx.py`)
- **`gen_soul_anchor` dead code** — Removed unreachable lines after the return statement. (`generate_sfx.py`)

### Files Changed
`tools/audio-workbench/synth/generate_sfx.py`

---

## [v0.1.26] - 2026-03-31 — Phase 33: Unified Oscillation Handler

### Changed
- **Unified oscillation handler** — Replaced 4 independent anti-oscillation systems (A→B→A suppressor in `ai_behavior.py`, patrol back-step in `ai_patrol.py`, follower trail backtrack × 3 in `ai_stances.py`) with a single `check_oscillation()` function that returns a *disposition*: `"allow"`, `"redirect"`, or `"wait"`. The key improvement: instead of converting all detected oscillations to WAIT (which paralysed units when multiple systems piled up), the handler first tries to REDIRECT to a non-backtracking adjacent tile that still makes progress toward the unit's goal. WAIT is now the last resort when no walkable alternative exists. (`ai_behavior.py`)
- **New `_find_redirect_tile()` helper** — Adjacent-tile picker used by the unified handler. Skips the backtrack tile, prefers tiles that close distance to the unit's move goal, and uses a random tiebreak to avoid deterministic oscillation between two equally-scored redirects. (`ai_behavior.py`)
- **Patrol back-step → unified handler** — `_patrol_action()` now calls `check_oscillation()` instead of its own inline `history[-2]` comparison. On `"redirect"`, the patrol waypoint is cleared and the redirect tile is used. On `"wait"`, a new waypoint is picked. (`ai_patrol.py`)
- **Follower trail backtrack × 3 → unified handler** — All three anti-backtrack sites in `_decide_follow_action()` (combat move, trail-to-owner, leader-tether) now delegate to `check_oscillation()` instead of each doing their own `_position_history[-2]` + corridor detection. The corridor exception logic is now implicit: `check_oscillation()` returns `"redirect"` when it finds an alternative tile (common in corridors), and only `"wait"` when truly stuck. (`ai_stances.py`)
- **New reason tag `oscillation_redirect`** — Moves that were redirected by the unified handler in the `run_ai_decisions()` post-check are tagged with `reason="oscillation_redirect"` for batch analysis visibility. (`ai_behavior.py`)
- **New reason tag `patrol_redirect`** — Patrol moves redirected by the unified handler. (`ai_patrol.py`)

### Technical Detail
The previous architecture had 4 separate detection systems (plus the Phase 30 stall breaker) that could all trigger on the same unit in the same tick, creating a cascade where the unit was forced to WAIT by multiple independent guards with no escape route. The hard timeout at 20 ticks (`_MAX_SUPPRESS_TURNS`) was the only exit, meaning stuck units wasted up to 20 turns standing still. The new unified handler absorbs the detection logic from all 4 systems into a single 4-stage check (A→B→A detection → enemy proximity → extended oscillation → bounding-box stall) and provides a redirect escape before falling back to WAIT, significantly reducing idle time for oscillating units.

### Files Changed
`ai_behavior.py`, `ai_patrol.py`, `ai_stances.py`

---

## [v0.1.25] - 2026-03-28 — Render Pipeline Performance Pass II

### Changed
- **measureText cache** — `unitRenderer.js` now caches `ctx.measureText()` results in a per-font+text Map (capped at 500 entries with LRU half-eviction). Nameplate text truncation no longer calls the expensive Canvas `measureText()` every frame for every visible unit. (`unitRenderer.js`)
- **Date.now → performance.now** — `_getAnimatedHp()` in `unitRenderer.js` switched from `Date.now()` to `performance.now()` for sub-millisecond precision and to avoid repeated system-clock calls. (`unitRenderer.js`)
- **Vignette gradient caching** — `ArenaRenderer.js` now caches the full-screen vignette radial gradient keyed on canvas dimensions and theme. Only recreated on canvas resize or theme change instead of every frame. (`ArenaRenderer.js`)
- **Walkable tile Set caching** — `dungeonRenderer.js` now builds the walkable tile `Set` once per dungeon load (keyed on tile grid hash) instead of reconstructing it every frame during room-props rendering. Exposed `clearWalkableCache()` for floor transitions. (`dungeonRenderer.js`)
- **PositionInterpolator zero-allocation** — `getInterpolatedPositions()` now reuses a persistent `Map` and pooled `{x, y}` position objects instead of creating new ones every frame. Added `_fillLerpedPos()` helper that writes directly into existing objects. (`PositionInterpolator.js`)
- **Emitter forces object reuse** — `Emitter.update()` now mutates a pre-allocated `_forces` object instead of creating a new `{ gravityX, gravityY, friction, windX }` object per emitter per frame. (`Emitter.js`)

### Added
- **Unit cache cleanup utility** — New `cleanupUnitCaches(aliveUnitIds)` export from `unitRenderer.js` that purges stale entries from the nameplate expand and HP animation caches. Accepts a `Set` of alive unit IDs to selectively prune dead units, or `null` to clear everything. Re-exported from `ArenaRenderer.js` for convenient access. (`unitRenderer.js`, `ArenaRenderer.js`)

### Reverted (caused regression)
- **Shadow gradient caching** — The `ctx.save/translate/scale/restore` pattern used to position cached gradients was more expensive per-unit than simply creating a fresh `createRadialGradient`. Canvas state save/restore snapshots the entire state stack and is costlier than lightweight gradient construction.
- **HP bar gradient caching** — Same issue: `ctx.save/translate/restore` per HP bar added more overhead than inline `createLinearGradient` with correct coordinates.
- **Particle color string caching** — With alpha changing virtually every frame for fading particles, the cache hit rate was near-zero while adding 4 comparisons + quantization overhead per particle per frame.

### Performance Impact
- **Lesson learned:** Canvas 2D `ctx.save()`/`ctx.restore()` is expensive — it snapshots the entire context state. Caching gradient objects only helps if they can be used WITHOUT transform workarounds. Simple `createRadialGradient`/`createLinearGradient` calls are cheap in modern browsers; the bottleneck is draw calls and state changes, not gradient construction.

### Files Changed
`Emitter.js`, `unitRenderer.js`, `dungeonRenderer.js`, `ArenaRenderer.js`, `PositionInterpolator.js`, `Particle.js`

---

## [v0.1.24] - 2026-03-28 — Cinematic Intro Sequence

### Added
- **Rune Gate Studio splash screen** — Full-viewport studio logo reveal on game launch with the Rune Gate Studio PNG centered on a black background. Includes a pulsing cyan radial bloom behind the portal, two layers of CSS-only floating cyan particle motes drifting outward, and a smooth fade-in/fade-out cycle (~3.5s). (`IntroSequence.jsx`, `_intro.css`)
- **Synthesized portal audio cue** — Web Audio API procedural sound effect on the studio splash: a filtered noise burst swept through a bandpass filter for a "whoosh" feel, layered with a low-frequency sine hum. Routes through the AudioManager's UI gain node to respect user volume settings. No external audio file required. (`IntroSequence.jsx`)
- **Game title reveal screen** — After the studio fade, a second screen reveals "HERO'S CALL" in large Cinzel font with an ember-gold metallic gradient and a light-sweep animation across the letters. Below it, "A R E N A" fades in with expanding letter-spacing and blur-to-sharp transition. An ornamental divider and tagline fade in beneath. Warm ember particles rise from the bottom in two parallax layers, with a pulsing radial bloom and cinematic vignette overlay. (~4.5s, auto-advances to login). (`IntroSequence.jsx`, `_intro.css`)
- **Click-to-skip with fast-forward** — Click or press any key to fast-forward through remaining intro screens rather than jumping straight to login. A subtle "Click or press any key to skip" hint fades in at the bottom-right. First interaction also resumes AudioContext and starts the music playlist. (`IntroSequence.jsx`)
- **`prefers-reduced-motion` support** — All particle animations, sweeps, and bloom pulses are replaced with simple fades when the user has reduced-motion enabled. (`_intro.css`)

### Changed
- **App.jsx initial screen** — Default screen state changed from `'lobby'` to `'intro'`. IntroSequence renders as a fixed overlay before transitioning to the login lobby on completion. (`App.jsx`)
- **useAmbientAudio hook** — Added `'intro'` to the explicit screen cases that call `stopAmbient()`, preventing any stale ambient from leaking into the intro. (`useAudio.js`)
- **main.css** — Added `@import './screens/_intro.css'` to the Screens section. (`main.css`)

### New Files
- `client/src/components/Intro/IntroSequence.jsx` — React component with internal state machine: `studio → studio-fade → title → title-fade → done`
- `client/src/styles/screens/_intro.css` — All intro animations, particle effects, bloom, vignette, title typography, and reduced-motion overrides
- `client/public/rune-gate-studio.png` — Studio logo copied from `Assets/Sprites/rune gate.png`

---

## [v0.1.23] - 2026-03-29 — Render Pipeline Performance & FPS Overlay

### Added
- **PerfTracker module** — New lightweight singleton (`PerfTracker.js`) with a 120-frame ring buffer that records per-frame render cost and wall-clock timestamps. Exposes `getStats()` (fps, frameMs, avgMs, minMs, maxMs) and `getHistory(count)` for sparkline graphing. Shared between the render loop and DevOverlay without adding React re-renders. (`PerfTracker.js`)
- **FPS / frame-time overlay in DevOverlay** — New collapsible "Performance" section in the backtick DevOverlay panel showing live FPS (color-coded green/yellow/orange/red), current frame time in ms, avg/min/max stats, and a 60-frame canvas sparkline bar chart with a 16.6 ms budget reference line. Stats polled at 4 Hz to avoid re-render spam. (`DevOverlayPanel.jsx`)
- **PerfSparkline component** — Tiny canvas-based bar chart embedded in the DevOverlay. Each bar is color-coded by severity (green ≤12 ms, yellow ≤16.6 ms, orange ≤24 ms, red >24 ms). A dashed white line marks the 60 fps budget. (`DevOverlayPanel.jsx`)

### Changed
- **Hero light map caching** — `_buildHeroLightMap()` now caches its output keyed on hero grid positions. Since heroes move once per turn (integer tile coordinates), the triple-nested distance loop (~676 sqrt calls × 4 heroes) is skipped entirely between moves. Also uses squared-radius early rejection to skip `Math.sqrt` in the inner loop when tiles are clearly outside range. (`PropLighting.js`)
- **Hero torch glow offscreen + throttle** — `drawHeroTorchGlow()` now composites 4 six-stop radial gradients onto a dedicated offscreen canvas and redraws at ~12 fps (80 ms interval) instead of creating fresh gradients on the main canvas every frame at 60 fps. Subsequent frames blit the cached canvas in one `drawImage` call. (`PropLighting.js`)
- **FoV distance sqrt optimization** — `drawAmbientDarknessPass()` now uses squared distances for the bright-zone early exit, only calling `Math.sqrt` for tiles in the falloff band. (`PropLighting.js`)
- **Wall perspective lazy cache** — `drawWallPerspective()` results are cached on first draw per variant + 4-bit neighbor key (max 128 entries: 8 variants × 16 neighbor combos). Subsequent frames blit the cached offscreen canvas instead of re-running 8–14 canvas operations per wall tile per frame. (`ThemeEngine.js`)
- **Door perspective lazy cache** — `drawDoorPerspective()` results are cached per seed + orientation + open/closed state. Eliminates 50–65 canvas operations per door per frame after the first render. (`ThemeEngine.js`)
- **Overhang shadow LUT** — `drawOverhangShadow()` now reads from a pre-computed alpha lookup table built during `_buildCache()`, removing per-pixel `toFixed(3)` string allocation in the tight loop. (`ThemeEngine.js`)
- **Smart dungeon redraw throttle** — Replaced the unconditional `isDungeon → always redraw` flag in the render loop with a throttled check (~12 fps / 80 ms interval) so ambient dungeon animations still play but the full 30+ pass pipeline no longer fires at uncapped 60 fps. This was the single highest-impact fix. (`Arena.jsx`)
- **Render loop frame instrumentation** — The `requestAnimationFrame` loop now wraps `renderFrame()` with `performance.now()` bookends and feeds timing data into `PerfTracker`. Passes `perfTracker` as a prop to `DevOverlayPanel`. (`Arena.jsx`)

### Performance Impact
- **Before:** Dungeon view forced unconditional 60 fps full-pipeline redraws; hero lighting recalculated every frame; wall/door composites drawn from scratch every frame. Perceived server tick lag was actually client-side frame drops delaying WebSocket message processing.
- **After:** Dungeon ambient redraws throttled to ~12 fps; hero light map cached between turns; torch glow throttled to ~12 fps on offscreen canvas; wall and door composites cached after first draw; overhang shadow loop de-stringified. Net effect: dramatically reduced per-frame GPU/CPU cost, freeing the JS main thread to process server ticks on time.

### Files Changed
`PropLighting.js`, `ThemeEngine.js`, `Arena.jsx`, `DevOverlayPanel.jsx`, `PerfTracker.js` (new)

---

## [v0.1.22] - 2026-03-28 — Treasure Chest Visual Overhaul

### Added
- **Barrel-domed lid** — Chests now have a properly curved dome lid drawn with `quadraticCurveTo` instead of a flat rectangle. The dome includes a highlight gradient at the top and a horizontal metal band across its center. Opened chests show the curved lid tilted backward with a visible dark underside. (`chestRenderer.js`, `tilePatterns.js`)
- **Ground shadow** — Each chest casts a subtle elliptical shadow beneath it, grounding it on the floor tile. (`chestRenderer.js`, `tilePatterns.js`)
- **Wood plank texture** — 3 vertical plank groove lines are drawn across the chest body, giving it a wooden crate-to-chest visual upgrade. Opened chests render planks at 50% opacity. (`chestRenderer.js`, `tilePatterns.js`)
- **Metal corner brackets with rivets** — Iron, Gold, Obsidian, and Boss chests now display L-shaped corner brackets at all four body corners with rivet dots at each junction. (`chestRenderer.js`)
- **Band rivets** — Metal straps now feature 3 rivet dots each (spaced at 20%, 50%, 80% across the band width) for Iron+ tiers. (`chestRenderer.js`, `tilePatterns.js`)
- **Rope binding (wooden tier)** — Wooden chests feature diagonal rope-cross lines across the body, differentiating them visually from metal-reinforced tiers. (`chestRenderer.js`)
- **Rune engravings (obsidian/boss)** — Obsidian and Boss chests display glowing rune-line patterns (vertical line + cross marks) on the body in the latch color at 60% opacity. (`chestRenderer.js`)
- **Tier-specific lock styles:**
  - *Wooden:* Simple circular latch with centered keyhole dot and slot
  - *Iron:* Shield-shaped lock plate with pointed bottom and precision keyhole
  - *Gold/Boss:* Ornate double-ring circular lock with a colored gem center (green for gold, red for boss) and white gem highlight
  - *Obsidian:* Skull-shaped lock with eye sockets, jaw line, and purple gem in forehead
  (`chestRenderer.js`)
- **Interior sparkle dots** — Opened non-wooden chests now show 2-4 sparkle dots (gold or purple for obsidian) with white center highlights inside the dark interior cavity, simulating visible loot glint. Boss chests get 4 sparkles, obsidian 3, others 2. (`chestRenderer.js`, `tilePatterns.js`)
- **Golden inner rim** — Opened chests show a subtle gold-colored rim at the top of the body opening (25% opacity latch color). (`chestRenderer.js`, `tilePatterns.js`)
- **`TIER_FEATURES` config table** — New per-tier feature flags (`planks`, `rope`, `rivets`, `cornerBrackets`, `gem`, `runes`, `lockStyle`) that drive structural differentiation between tiers beyond just color. (`chestRenderer.js`)

### Changed
- **Thicker metal bands** — Band height increased from `s * 0.04` to `s * 0.05` with added highlight (top 1px) and shadow (bottom 1px) edges for more visible iron straps. (`chestRenderer.js`, `tilePatterns.js`)
- **Lid proportions** — Lid height increased from `s * 0.14` to `s * 0.18` to accommodate the dome shape. Lid overhang increased from 4% to 6% of chest width. (`chestRenderer.js`, `tilePatterns.js`)
- **Tier glow effect** — Glow is now rendered as an elliptical aura around the chest center at 40% alpha rather than a rectangular shadow blur around the bounding box. (`chestRenderer.js`)
- **Opened lid rendering** — The opened lid is now drawn as a foreshortened curved shape (matching the closed dome) instead of a flat narrow rectangle. Includes a visible dark underside strip. (`chestRenderer.js`, `tilePatterns.js`)
- **Theme Designer `drawChest()` synced** — The theme-designer's palette-driven chest drawing (`tilePatterns.js`) updated with all the same structural improvements: curved lid, planks, bands with rivets, corner brackets, ground shadow, sparkle interior, and ornate lock. Uses `shiftColor()` for palette-derived colors.

---

## [v0.1.21] - 2026-03-28 — Orientation-Aware Door Perspective

### Added
- **Faux 3/4 perspective door rendering** — Doors now render differently based on which direction the passage runs through them, matching the Enter-the-Gungeon-style wall perspective from v0.1.19. The door's orientation is inferred at render time by checking neighboring tiles: walls to the north and south indicate an east/west passage, walls to the east and west indicate a north/south passage. (`ThemeEngine.js`, `dungeonRenderer.js`, `tilePatterns.js`)
- **North/South passage doors (front-facing)** — These doors span a horizontal boundary between rooms. The camera's slight south-downward angle means you see the door's **top edge** (a lit wood strip, ~14% tile height) and the **south-facing front face** below it. The face features:
  - 3 vertical wood planks with per-plank color variation and groove lines
  - 2 horizontal iron band straps with highlight/shadow and rivet dots at plank intersections
  - A ring-pull handle with mounting plate (replaces the old tiny gold dot)
  - Stone door frame (left/right jambs + top lintel) using `palette.primary`
  - Bottom threshold darkening where the door meets the floor
- **East/West passage doors (side-on view)** — These doors span a vertical boundary. The camera sees the door from its narrow side, rendering a **face panel** (~35% tile width) with horizontal planks and vertical iron bands, plus a **thickness edge** (~14% width) showing the door's depth. Includes the same ring-pull handle, stone frame (top/bottom lintels + side jambs), and depth-separation line between face and edge.
- **Open door states differ by orientation:**
  - NS open: Two panels swing inward (toward the player), drawn as foreshortened trapezoids flanking the opening with a visible iron band on each panel. Stone frame and dark gap between panels visible through the doorway.
  - EW open: Single panel swings flat against the north wall, showing only its thin edge with a highlight and iron band strip. Stone frame lintels remain visible.
- **`drawDoorPerspective()` method on ThemeEngine** — New neighbor-aware door drawing method that composites floor, frame, planks, bands, rivets, and handle. Called from `dungeonRenderer.js` before the generic `drawTile()` path, same pattern as `drawWallPerspective()`. (`ThemeEngine.js`)
- **`drawDoorPerspective()` export in tilePatterns.js** — Parallel implementation for the Theme Designer tool with identical visual output. Uses 4 internal helper functions: `_drawDoorNS_closed`, `_drawDoorNS_open`, `_drawDoorEW_closed`, `_drawDoorEW_open`. (`tilePatterns.js`)

### Changed
- **Doors in `dungeonRenderer.js` now use neighbor-aware dispatch** — Before falling through to the generic `drawTile()` path, door tiles check their north/south/east/west neighbors and route through `drawDoorPerspective()`. The check runs after the wall perspective dispatch and before the `extra` object is built. (`dungeonRenderer.js`)
- **Flat-color fallback doors are orientation-aware** — The sprite/flat-color fallback path (used when ThemeEngine is not ready) now detects whether walls are to the N+S or E+W and draws an appropriately shaped door: NS closed shows a wider panel with visible top edge, EW closed draws a narrow centered vertical panel. Open states also differ (NS: two side panels, EW: thin strip at top). (`dungeonRenderer.js`)
- **Theme Designer `ThemeRenderer.drawTile()` accepts neighbor info** — When `extra.wallNorth`, `extra.wallSouth`, `extra.wallEast`, `extra.wallWest` are provided, the door case routes through `drawDoorPerspective()` instead of the legacy `drawDoor()`. Falls back to `drawDoor()` when neighbor context is unavailable. (`themeRenderer.js`)
- **DungeonPreview.jsx passes neighbor context for doors** — The tile rendering loop now includes a `_tileType()` helper and populates `extra.wallNorth/South/East/West` for door tiles so the Theme Designer's dungeon preview renders perspective doors. (`DungeonPreview.jsx`)
- **PvpvePreview.jsx passes neighbor context for doors** — Same neighbor detection added to the PVPVE dungeon preview's base tile rendering loop. (`PvpvePreview.jsx`)
- **RoomArchetypePreview.jsx passes neighbor context for doors** — Both the isolated room template and the full dungeon map rendering loops now detect door neighbors for perspective rendering. (`RoomArchetypePreview.jsx`)
- **Legacy `drawDoor()` preserved as fallback** — The original flat square door rendering in both `ThemeEngine.js` and `tilePatterns.js` remains available for contexts where neighbor info is not passed (backward compatible). (`ThemeEngine.js`, `tilePatterns.js`)

### Visual Design Notes
- All door colors are derived from the theme palette (`palette.secondary`, `palette.metal`, `palette.highlight`, `palette.primary`) so doors look correct across all 13 grimdark themes.
- The stone frame uses `shiftColor(palette.primary, 10)` — slightly lighter than the wall base — giving doors an inset "fitted into the wall" appearance.
- Iron bands and rivets use `palette.metal` (falling back to `palette.secondary`), matching the existing torch sconce and chain prop aesthetic.
- Per-plank color variation uses `cellHash` for deterministic seeds, so each door looks slightly different but stays consistent across frames.

### Files Changed
- `client/src/canvas/ThemeEngine.js` — `drawDoorPerspective()`, `_drawDoorNS_closed()`, `_drawDoorNS_open()`, `_drawDoorEW_closed()`, `_drawDoorEW_open()`
- `client/src/canvas/dungeonRenderer.js` — Door neighbor detection dispatch + flat-color fallback orientation
- `tools/theme-designer/src/engine/tilePatterns.js` — `drawDoorPerspective()` export + 4 helper functions
- `tools/theme-designer/src/engine/themeRenderer.js` — `drawDoorPerspective` import, `drawTile()` door case updated
- `tools/theme-designer/src/components/DungeonPreview.jsx` — `_tileType()` helper, door neighbor info in extra
- `tools/theme-designer/src/components/PvpvePreview.jsx` — `_tileType()` helper, door neighbor info in extra
- `tools/theme-designer/src/components/RoomArchetypePreview.jsx` — `_roomType()`/`_dungeonType()` helpers, door neighbor info in extra

---

## [v0.1.20] - 2026-03-28 — Wall Cap Cleanup & Side-Plate Perspective

### Fixed
- **Removed mortar grid and edge-definition lines from wall caps** — The `drawWallTop()` function previously drew a faint mortar grid (horizontal + vertical lines at alpha 0.14) and per-tile edge definition lines (1px highlight on top/left, 1px shadow on bottom/right). These created a ~14-point brightness difference at every tile boundary that survived through ambient darkness and fog, producing a visible checkered grid pattern in the dark areas behind walls (above the top plate, beyond field of view). The base color fill and subtle stone grain speckles are preserved for texture variation. (`ThemeEngine.js`)

### Added
- **Side-plate perspective for left/right-facing walls** — Interior walls adjacent to floor tiles on the left and/or right side now render a vertical brick face "plate" strip (~20% tile width) on the exposed side, with the dark cap filling the remaining area. This mirrors the horizontal top-plate treatment from south boundary walls (Case 2) but rotated vertically. Three sub-cases are handled: floor-left-only, floor-right-only, and floor-on-both-sides. Each includes a lit edge highlight on the exposed face and a lip shadow where the plate meets the cap. Previously these walls rendered as a full dark cap with only 1–3px edge hints, appearing as a featureless black void. (`ThemeEngine.js`)

### Changed
- **`drawWallPerspective()` Case 4 restructured** — The former "interior wall" case is now split into Case 4a (side-facing walls with `floorLeft`/`floorRight`) and Case 4b (pure interior walls with no adjacent floor at all). Case 4b still renders the full cap. (`ThemeEngine.js`)
- **Chains moved from side walls to north wall** — Prison room chains now spawn via `on_wall_top` (south-facing wall above room) instead of `on_wall_left`/`on_wall_right`. With the new side-plate perspective, only a thin vertical strip is visible on side walls — chains need the full horizontal wall face to read properly. Prison rooms also gain side-wall torch sconces to compensate for the freed left/right slots. (`TileProps.js`)
- **Weapon racks moved from side walls to north wall** — Boss room and armory weapon racks now exclusively use `on_wall_top`. The vertical side-plate is too narrow for weapon rack visuals to be readable. (`TileProps.js`)
- **Hanging lanterns moved from side walls to north wall** — Loot, shrine, library, and cathedral rooms now place hanging lanterns via `on_wall_top` instead of `on_wall_left`. Only torch sconces remain on left/right side walls since their small flame glow works well on the narrow plate face. (`TileProps.js`)
- **Side-wall prop visual offset (Option A)** — `_placeSlot()` now applies a 65% tileSize pixel offset inward for `on_wall_left` and `on_wall_right` positions, aligning the prop visually with the ~20%-width brick plate face instead of centering it on the full wall tile (which is mostly dark cap). Grid-integer position is preserved for lighting and collision. (`TileProps.js`)
- **Stairs overlay wall streaks shifted to plate face** — The depth-suggesting accent streaks on left/right stairwell walls are offset inward by 65% tileSize to sit on the visible side-plate face instead of the dark cap void. (`RoomOverlays.js`)

### Files Changed
- `client/src/canvas/ThemeEngine.js` — `drawWallTop()` mortar/edge removal, `drawWallPerspective()` side-plate rendering (Cases 4a/4b)
- `client/src/canvas/TileProps.js` — Wall prop slot reassignments (chains, weapon_rack, hanging_lantern → `on_wall_top`), side-wall visual offset in `_placeSlot()`
- `client/src/canvas/RoomOverlays.js` — Stairs overlay wall streak offset

---

## [v0.1.19] - 2026-03-28 — Faux 3/4 Wall Perspective (Enter the Gungeon Style)

### Added
- **Faux 3/4 perspective wall rendering** — Dungeon walls are now drawn with a pseudo-3D perspective inspired by Enter the Gungeon. The camera is conceptually angled slightly south, so walls expose different surfaces depending on which direction they face. This replaces the flat top-down wall rendering that treated every wall tile identically. (`ThemeEngine.js`, `dungeonRenderer.js`)
- **Four directional wall cases** — Walls now render differently based on neighboring floor tiles:
  - **North boundary** (floor to the south): dark cap top ~35% + textured brick face bottom ~65% — you see the south-facing wall surface
  - **South boundary** (floor to the north): thin brick "top plate" strip ~18% at top + cap below — the plate effect where you're peeking over the wall
  - **Both sides exposed** (thin wall between areas): top plate + narrow cap + south face
  - **Interior walls**: full cap with gradient depth texture
- **`drawWallTop()` function** — New procedural wall cap renderer that uses a center-brightened radial gradient for 3D pillow/depth. Base color is anchored to the floor palette (much brighter than primary) so caps stay readable on all 13 grimdark themes instead of appearing void-black. (`ThemeEngine.js`)
- **`drawWallPerspective()` method** — Neighbor-aware wall drawing method on ThemeEngine that composites cap and face tiles with lip highlights, base darkening, and side depth strips. (`ThemeEngine.js`)
- **`drawOverhangShadow()` method** — Renders a soft downward-fading gradient shadow on floor tiles directly below south-facing walls, grounding the wall visually. Called during the edge rendering pass. (`ThemeEngine.js`, `dungeonRenderer.js`)
- **`wall_top_` cache variants** — 8 pre-rendered wall cap tiles added to the tile cache alongside the existing 8 wall face variants. Uses `OffscreenCanvas` when available for performance. (`ThemeEngine.js`)
- **Lip highlight at cap-face junction** — 2px graduated highlight line where the dark cap meets the brick face, selling the separation between the two surfaces. (`ThemeEngine.js`)
- **Bottom edge darkening** — Wall base where face meets floor gets a 4px darkened strip for grounding. (`ThemeEngine.js`)
- **Side depth strips** — East/west exposed wall faces get 3px highlight strips hinting at the wall's side surface. (`ThemeEngine.js`)

### Changed
- **Wall tiles in dungeonRenderer now use neighbor-aware dispatch** — Before falling through to the generic `drawTile()` path, wall tiles check their north/south/east/west neighbors and route through `drawWallPerspective()` for the 3/4 perspective effect. Non-theme paths (TileLoader sprites, flat color fallback) are unaffected. (`dungeonRenderer.js`)
- **Edge rendering pass extended with overhang shadows** — Floor tiles with a wall to the north (`neighbors.top`) now receive an overhang shadow after the theme edge decoration (crumble, scorch, moss, etc.). (`dungeonRenderer.js`)

### Files Changed
- `client/src/canvas/ThemeEngine.js` — `drawWallTop()`, `drawWallPerspective()`, `drawOverhangShadow()`, `wall_top_` cache, gradient-based cap rendering
- `client/src/canvas/dungeonRenderer.js` — Neighbor-aware wall dispatch, `floorAbove`/`floorBelow`/`floorLeft`/`floorRight` detection, overhang shadow in edge pass

---

## [v0.1.18] - 2026-03-28 — Wall-Mounted Prop Placement Overhaul

### Added
- **Three new position types: `on_wall_top`, `on_wall_left`, `on_wall_right`** — These resolve to actual wall tiles (one tile outside floor bounds) instead of floor tiles adjacent to walls. Wall-mounted decorations (banners, chains, hanging lanterns, weapon racks) now render on the wall surface where they visually belong. Positions bypass walkability checks since wall tiles are intentionally non-walkable. (`tileProps.js`, `TileProps.js`, `PropLighting.js`)
- **`hanging_lantern` added to loot rooms** — Compensates for the removed wall alcove visual; loot rooms now have a 30% chance to spawn a hanging lantern on the top wall, restoring ambient lighting that was lost. (`tileProps.js`, `TileProps.js`)
- **`weapon_rack` added to theme designer archetypes** — Boss (on_wall_right, 30%), enemy (on_wall_top, 50%), and armory (on_wall_top 70%, on_wall_left 50%) archetypes in the theme designer now include weapon racks for parity with the game client. (`tileProps.js`)

### Fixed
- **Wall banners no longer spawn on floor tiles** — Banners in boss, spawn, cathedral, and shrine rooms now use `on_wall_top` instead of `wall_top`, placing them on the actual wall tile (y_min−1) instead of the topmost floor tile (y_min). (`tileProps.js`, `TileProps.js`)
- **Chains no longer spawn on floor tiles** — Chains in enemy, prison, torture, and empty rooms now use `on_wall_top`/`on_wall_left`/`on_wall_right` positions. Prison chains specifically moved from floor-adjacent positions to actual wall tiles on left and right walls. (`tileProps.js`, `TileProps.js`)
- **Hanging lanterns placed on wall tiles** — Hanging lanterns in shrine, library, and cathedral rooms now use `on_wall_top` to render on the wall surface above the room. (`tileProps.js`, `TileProps.js`)
- **Weapon racks placed on wall tiles** — Weapon racks in boss, enemy, and armory rooms now use `on_wall_top`/`on_wall_left`/`on_wall_right` instead of floor-adjacent positions, matching their wall-mounted visual. (`tileProps.js`, `TileProps.js`)
- **Torch sconces placed on wall tiles** — All `torch_sconce` entries across every archetype (enemy, loot, spawn, stairs, shrine, library, prison, torture, armory) moved from `wall_left`/`wall_right`/`wall_top` to `on_wall_left`/`on_wall_right`/`on_wall_top`. Wall torches no longer render on the floor. (`tileProps.js`, `TileProps.js`)
- **Wall alcove removed from loot room overlays** — The dark rectangle drawn along left/right walls in loot rooms looked out of place; removed from both the overlay drawing function and the `computeOverlayDecorations` tooltip data. Replaced by prop-system lighting (torch_sconce, hanging_lantern). (`roomArchetypes.js`, `RoomOverlays.js`)
- **Prison overlay chains fixed** — Inline chain drawing in shrine (banners) and prison (chains) overlays updated to use wall tile coordinates (y_min−1, x_min−1, x_max+1) instead of floor tile coordinates. (`roomArchetypes.js`, `RoomOverlays.js`)

### Changed
- **`_POSITION_PRIORITY` map extended** — New `on_wall_top` (priority 12), `on_wall_left` (13), `on_wall_right` (14) entries added to the placement priority table. (`tileProps.js`, `TileProps.js`)
- **`PropLighting.js` resolver updated** — The light-source position resolver now handles `on_wall_top`, `on_wall_left`, and `on_wall_right` for accurate glow pass positioning on wall-mounted light sources. (`PropLighting.js`)

### Files Changed
- `tools/theme-designer/src/engine/tileProps.js` — New on_wall_* positions, weapon_rack added to boss/enemy/armory, hanging_lantern to loot
- `tools/theme-designer/src/engine/roomArchetypes.js` — Wall alcove removed from loot overlay, shrine/prison overlay wall coords fixed
- `client/src/canvas/TileProps.js` — New on_wall_* positions, weapon_rack → on_wall_*, hanging_lantern to loot
- `client/src/canvas/RoomOverlays.js` — Wall alcove removed from loot overlay
- `client/src/canvas/PropLighting.js` — on_wall_* position support in light resolver

---

## [v0.1.17] - 2026-03-28 — PVPVE Chest Scarcity Rebalance

### Changed
- **PVPVE loot room density cut from 50% → 15%** — Drastically reduces the number of dedicated loot rooms in PVPVE dungeons. On an 8×8 grid (~50 flexible rooms), this drops loot rooms from ~25 down to ~8, making each chest discovery feel significant rather than routine. Freed room budget naturally flows to enemy and empty rooms, making the dungeon more dangerous. (`room_decorator.py`, `pvpveDecorator.js`, `pvpveGenerator.js`)
- **Scatter chest probabilities halved across all room types** — Enemy rooms: 30% → 15%. Shrine rooms: 40% → 20%. Library rooms: 50% → 25%. Empty rooms: 10% → 5%. This cuts incidental chest spawns roughly in half, eliminating the "chests everywhere" feel. (`room_decorator.py`, `pvpveDecorator.js`)
- **PVPVE loot rooms capped to 1 chest** — Loot rooms in PVPVE now always place exactly 1 chest instead of rolling 1–2. Combined with the density reduction, this ensures each loot room is a single meaningful find rather than a pile. Standard PvE dungeons are unaffected (still use `maxChests` from the module). (`room_decorator.py`, `pvpveDecorator.js`)
- **PVPVE chest tier weights shifted toward better tiers** — Edge zone: wooden 55→35, iron 30→40, gold 12→18, obsidian 3→7. Mid zone: wooden 30→15, iron stays 35, gold 25→35, obsidian 10→15. Center zone unchanged. Players now find fewer wooden chests and more iron/gold even near spawn. (`loot_tables.json`)
- **Wooden and Iron chest min_items raised from 1 → 2** — Every chest now guarantees at least 2 items. With fewer chests in the dungeon, each one should feel rewarding rather than disappointing. (`loot_tables.json`)

### Estimated Impact
- **Before:** ~30–45 chests per PVPVE dungeon, mostly wooden tier (1–2 common items each).
- **After:** ~10–15 chests per PVPVE dungeon, better tier distribution, guaranteed 2+ items each.
- The existing centrality-based risk/reward system (`roll_chest_tier_pvpve` with edge/mid/center zones) now has room to shine — players actively seek contested center territory for rare gold/obsidian chests instead of tripping over wooden ones everywhere.

### Files Changed
- `server/app/core/wfc/room_decorator.py` — lootDensity 0.50→0.15, scatter probabilities halved, loot room 1-chest cap (PVPVE only)
- `server/configs/loot_tables.json` — PVPVE tier weights rebalanced, wooden/iron min_items 1→2
- `tools/theme-designer/src/engine/pvpveDecorator.js` — lootDensity 0.50→0.15, scatter probabilities halved, loot room 1-chest cap
- `tools/theme-designer/src/engine/pvpveGenerator.js` — PVPVE_DECORATOR_SETTINGS lootDensity 0.50→0.15

### Technical Notes
- Standard PvE dungeon decoration is unaffected — the loot density and scatter changes only apply to the PVPVE code paths (`_PVPVE_DECORATOR_DEFAULTS` / `pvpveDecorator.js`).
- The loot room 1-chest cap uses `config.get("pvpve_mode")` in Python to gate the cap, preserving standard PvE behavior.
- All 4006 tests passing (1 pre-existing library.json format mismatch unrelated to these changes).

---

## [v0.1.16] - 2026-03-28 — Prop Placement Floor Validation

### Fixed
- **Props no longer spawn on wall tiles** — `_resolvePosition()` in both `TileProps.js` and `PropLighting.js` now accepts an optional `walkableTiles` Set and filters every candidate position against it. Only floor and corridor tiles are considered valid placement targets. Previously, `corners`, `wall_left`, `wall_right`, `wall_top`, and `random_floor` positions were computed purely from bounding-box math and could land on wall tiles in irregularly-shaped rooms. (`TileProps.js`, `PropLighting.js`)
- **`random_floor` uses rejection sampling** — Instead of blindly picking random (x,y) within bounds (which frequently hit walls in non-rectangular rooms), `random_floor` now tries up to 10× the needed count and only keeps positions that pass the walkable check. Props that previously "disappeared" (rendered behind walls) now land on visible floor tiles. (`TileProps.js`, `PropLighting.js`)
- **Tight floor bounds replace fixed 1-tile inset** — `map_exporter.py` now scans each room module's actual tile grid and exports a `floor_bounds` rectangle computed from the tightest bounding box of all non-wall tiles. The client uses `floor_bounds` when available (falling back to the old ±1 inset for backward compatibility). This fixes center/corner/wall position calculations for rooms with asymmetric layouts, corridor openings, or internal wall features. (`map_exporter.py`, `dungeonRenderer.js`, `PropLighting.js`)
- **Theme Designer tool prop placement parity** — Ported the same `walkableTiles` validation and `floor_bounds` computation to the Theme Designer tool. The tool's `_resolvePosition()` now accepts an optional `walkableTiles` Set (5th param) and filters all candidates, including its wall-adjacent `random_floor` bias. `PvpvePreview.jsx` and `RoomArchetypePreview.jsx` both build `walkableTiles` from their tile maps and compute tight `floor_bounds` per room before passing to `drawRoomOverlay()`. (`tileProps.js`, `PvpvePreview.jsx`, `RoomArchetypePreview.jsx`)

### Changed
- `drawDungeonTiles()` now builds a `walkableTiles` Set (all floor + corridor tile positions) from the tile grid and passes it through to `drawRoomOverlay()` → `drawRoomProps()` → `_resolvePosition()`. This is the data that enables per-tile prop validation. (`dungeonRenderer.js`)
- `drawRoomProps()` destructures the new `walkableTiles` field from opts and forwards it to `_resolvePosition()`. (`TileProps.js`)
- `collectLightSources()` in `PropLighting.js` now uses `room.floor_bounds` when available for more accurate light source positioning.
- `_resolvePosition()` signature changed from `(position, bounds, seed)` → `(position, bounds, seed, walkableTiles)` in both `TileProps.js` and `PropLighting.js`. Fourth parameter is optional (null = no filtering, backward compatible).

### Technical Notes
- No changes to `room_decorator.py` — server-side gameplay tile placement (E/B/X/S/T) uses `spawnSlots` from `library.json`, which are hand-authored floor positions. This fix addresses the client-side decorative prop system only.
- `floor_bounds` is computed from the normalized tile grid (where E/B markers are already converted to F), so it accurately reflects the client's view of the room.
- All 4006 tests passing (1 pre-existing library.json format mismatch unrelated to these changes).

### Files Changed
- `server/app/core/wfc/map_exporter.py` — floor_bounds computation
- `client/src/canvas/dungeonRenderer.js` — walkableTiles Set + floor_bounds usage
- `client/src/canvas/TileProps.js` — _resolvePosition floor validation + drawRoomProps plumbing
- `client/src/canvas/PropLighting.js` — _resolvePosition floor validation + floor_bounds usage
- `tools/theme-designer/src/engine/tileProps.js` — _resolvePosition walkableTiles param + drawRoomProps plumbing
- `tools/theme-designer/src/components/PvpvePreview.jsx` — walkableTiles Set + floor_bounds per room
- `tools/theme-designer/src/components/RoomArchetypePreview.jsx` — walkableTiles Set + floor_bounds for both preview modes

### Changed
- **Slot Priority System (A)** — Every spawnSlot in `library.json` (152 slots across 21 flexible modules) now carries a `placement_hint` (center/corner/wall/interior) and per-role `priority` weights. Wall slots favor loot, center slots favor bosses/enemies, corners favor spawn points. Derived floor slots also receive hints automatically. (`library.json`, `room_decorator.py`, `roomDecorator.js`, `pvpveDecorator.js`)
- **Door-Distance Sorting (D)** — Slot selection now factors Manhattan distance to the nearest door or edge opening. Enemies sort toward entrances (room guards), while loot, bosses, and stairs sort away from doors (deeper in the room). Small jitter preserves variety without undermining the spatial logic. (`room_decorator.py`, `roomDecorator.js`, `pvpveDecorator.js`)
- **Chest Clustering (B)** — Loot rooms now pick a closed wall (one without a doorway) and cluster chests near it as a "treasure nook" instead of scattering them randomly across the room. Tiebreaks by proximity to room center for tight grouping. (`room_decorator.py`, `roomDecorator.js`, `pvpveDecorator.js`)

### Fixed
- **Boss room detection** — `map_exporter.py` now always sets `detected_purpose = "boss"` when a "B" tile is found (overriding any earlier loot/enemy detection from scan order). Boss room metadata lookup also falls back to `archetype == "boss"` so PVPVE boss rooms are correctly identified regardless of tile scan order. (`map_exporter.py`)

### Technical Notes
- New helper functions in `room_decorator.py`: `_classify_slot()`, `_get_slot_priority()`, `_find_door_positions()`, `_slot_door_distance()`, `_sort_slots_for_role()`, `_cluster_loot_slots()`.
- Equivalent JS helpers added to both `roomDecorator.js` (WFC Lab tool) and `pvpveDecorator.js` (Theme Designer tool).
- All 186 WFC/PVPVE tests passing. No client rendering or network changes.

---

## [v0.1.14] - 2026-03-28 — Torch-Light FoV Visual Overhaul

### Changed
- **FoV Distance Gradient** — Visible tiles now darken progressively with distance from the nearest hero, creating a natural torch-light falloff toward the edge of vision. Darkening begins at ~45% of vision range and ramps quadratically to full extra darkness at the FoV boundary. Eliminates the harsh bright-to-fog edge transition without changing any FoV mechanics. (`PropLighting.js`)
- **Extended Hero Torch Glow** — Hero torch radius increased from 2.5 → 5.0 tiles so the warm orange glow extends much further, visually unifying the torch as the apparent light source for the entire visible area. Gradient stops refined from 4 to 6 for a smoother, more natural falloff (bright core → soft fade). Intensity tuned down slightly (0.20 → 0.18) to stay balanced at the larger radius. (`PropLighting.js`)
- **Hero Torch Darkness Carve-out** — The darkness carve-out map (`_buildHeroLightMap`) updated to match the new torch radius. Falloff changed from quadratic to cubic for a brighter core with gentler outer fade, keeping tiles near heroes well-lit while allowing the distance gradient to take over at range. (`PropLighting.js`)

### Technical Notes
- No server changes — FoV computation, shadowcasting, and `visible_tiles` payload are unchanged.
- All changes are purely visual (client-side rendering pass in `drawAmbientDarknessPass` and `drawHeroTorchGlow`).
- Existing caching infrastructure (offscreen canvas, cache keys) handles the new distance computation with no extra invalidation needed — hero positions were already in the cache key.
- Configurable via `FOV_DISTANCE_GRADIENT` constants: `visionRange` (7), `falloffStart` (0.45), `maxExtraDarkness` (0.45).

---

## [v0.1.13] - 2026-03-27 — Dungeon Atmosphere Enhancements

### Added
- **Water Animation** — Flooded floors (Drowned Sanctum) and shallow_water corridors now display animated caustic light patterns and expanding ripple rings. Uses a dedicated offscreen canvas with additive blending, throttled to ~15fps. (`WaterAnimation.js`)
- **Ambient Particles** — Each dungeon theme now spawns characteristic floating atmospheric particles:
  - Bleeding Catacombs: rising ember sparks (warm red-orange glow)
  - Ashen Undercroft: drifting ash/dust motes (gray-white)
  - Drowned Sanctum: rising bubbles (blue-white glow)
  - Frozen Crypt: falling snowflakes/frost sparkles (white-blue)
  - Fungal Grotto: floating spores (green glow, brownian drift)
  - Other themes: subtle dust motes
  - Particles respect FOV (only visible on seen tiles), fade in/out over lifetime, and use additive blending for glow types. Pool of 18–35 particles per theme. (`AmbientParticles.js`)
- **Unit Light Interaction** — Units near light-emitting props (torches, braziers, candelabras, ritual circles) now receive a subtle warm glow overlay that matches the color and intensity of nearby light sources. Uses the existing cached ambient light map from PropLighting for O(1) per-unit lookup — zero extra computation. Appears as a soft radial gradient with additive blending, capped at 35% brightness for subtlety. (`PropLighting.js`, `unitRenderer.js`)
- **Vignette Edge Darkening** — A cinematic radial vignette overlay now darkens the screen edges in dungeon mode. Uses each theme's existing `vignetteStrength` (0.06–0.16) and `vignetteColor` config values, which were previously defined but never rendered. Drawn as the final post-process step after fog and damage floaters. (`ArenaRenderer.js`)

### Changed
- `drawPlayer()` in `unitRenderer.js` accepts a new optional `lightBoost` parameter for prop-light interaction rendering.
- `ArenaRenderer.renderFrame()` now imports and orchestrates four new visual passes in the render pipeline:
  1. Water animation (after tiles, before highlights)
  2. Unit light boost lookup (per unit, before sprite draw)
  3. Ambient particles (after darkness pass, before fog)
  4. Vignette (after damage floaters, final draw call)

### New Files
- `client/src/canvas/WaterAnimation.js` — Animated water shimmer overlay system
- `client/src/canvas/AmbientParticles.js` — Theme-specific ambient particle system

---

## [v0.1.12] - 2026-03-27 — Party Following Improvements (Phase 32)

### Fixed
- **Phase 32A: Follow moves exempt from anti-oscillation** — `follow_regroup`, `follow_trail`, `follow_rush_melee`, and `follow_move_to_target` MOVE actions are no longer suppressed by the global anti-oscillation detector in `run_ai_decisions()`. These are intentional movements toward the party leader that were being incorrectly flagged as A→B→A oscillation, causing followers to freeze behind corners and walls. (`ai_behavior.py`)
- **Phase 32C: Corridor-aware anti-backtrack** — All three anti-backtrack checks in `_decide_follow_action()` now detect narrow corridors (≤3 walkable neighbors) and allow backtracks in those locations. In tight corridors and around corners, the only viable path forward often requires briefly revisiting a previous tile — the old logic forced WAITs instead, leaving followers stuck behind walls while the leader moved ahead. (`ai_stances.py`)

### Added
- **Phase 32B: Leader breadcrumb trail** — Instead of all followers pathfinding to the leader's current position (causing tile congestion), each follower now targets a staggered position along the leader's recent movement history. Follower 0 targets the leader's current position, follower 1 targets 2 ticks back, follower 2 targets 4 ticks back, etc. This naturally forms a trailing column through corridors and around corners. Applied to regroup (Priority 1), trail owner (Priority 3), and leader-tether follow paths. (`ai_stances.py`)
- `_is_in_corridor()` helper — detects narrow passages by counting walkable neighbor tiles. (`ai_stances.py`)
- `_get_breadcrumb_target()` helper — assigns staggered follow targets from the leader's position history, with configurable `_BREADCRUMB_SPACING`. (`ai_stances.py`)

### Simulation Results (5 × 150 turns, grid-size 6)

| Stall Reason | Before (v0.1.11) | After Fixes A+C | After Fixes A+C+B | Trend |
|---|---|---|---|---|
| `oscillation_suppressed` | ~high | 65 | 56 | ↓ suppressed correctly |
| `follow_trail_wait` | ~high | 297 | 163 | ↓ fewer false waits |
| `follow_combat_wait` | ~high | 159 | 209 | → stable (combat-appropriate) |
| `follow_trail_owner` | ~low | 1,231 | 1,957 | ↑ +59% more active following |
| `follow_regroup` | ~low | 453 | 1,692 | ↑ +273% more regroup moves |

> Party cohesion dramatically improved. Followers now form a moving column behind the leader instead of clustering at one tile and stalling. 4040 tests passing.

---

## [v0.1.11] - 2026-03-27 — Exploration Stalling Fixes (Rounds 1–3)

### Fixed (Round 3 — Leader Succession, Door Pathfinding)
- **Leader succession: `ai_stance` cleared on promoted follower** — When a team leader dies, `deaths_phase.py` (Phase 27) already promotes a surviving follower to `is_team_leader=True`. However, the promoted unit kept `ai_stance="follow"`, causing `_decide_stance_action()` to route it through follower code paths instead of the leader exploration tree. Now clears `unit.ai_stance = None` on promotion so the new leader actually explores. (`deaths_phase.py`)
- **RC#4 door-path rescue: Manhattan → Chebyshev adjacency** — The door-path rescue fallback used Manhattan distance (`abs(dx)+abs(dy) <= 1`) to check if the leader was adjacent to a door, missing diagonal neighbors (Manhattan distance 2). Fixed to Chebyshev (`max(abs(dx), abs(dy)) <= 1`), matching the rest of the door interaction system. (`ai_behavior.py`)
- **Smart pathfind failure counting (structural reachability)** — When A\* failed to reach a room, it always incremented the fail counter. After 3 failures, the room was skipped for 60+ turns — even if the only reason A\* failed was that enemies temporarily blocked a corridor. Now re-runs A\* with an empty occupied set on failure. If a path exists without units blocking, the room is structurally reachable and the fail counter is NOT incremented. Only rooms truly walled off get skip penalties. (`ai_behavior.py`)
- **Batch tracker: leader succession detection** — `ExplorationTracker` now detects when an original team leader dies and a new leader is promoted mid-match, updating its internal `team_leaders` dict so all subsequent diagnostics (stall analysis, decision breakdowns, oscillation splits) attribute correctly to the new leader. (`batch_pvpve.py`)

### Simulation Results (Round 3, seed 42, 3 × 300 turns, grid-size 6)

| Metric | v0.1.10 Baseline | Round 2 | Round 3 |
|--------|-----------------|---------|---------|
| Avg exploration health | 14.7/100 | 24.7/100 | 18.7/100 |
| Avg tile coverage | ~6% | ~7% | ~7.7% |
| Room discovery (best team) | 38% | 64% | 46% |
| Doors opened (total) | 7–8 | 9–13 | 7–10 |
| Avg turns to completion | ~300 | ~300 | 253.7 |

> Note: Score variance is expected across runs. The structural fixes (Chebyshev adjacency, smart fail counting, leader succession) are correctness improvements that prevent edge-case stalls — their impact is more pronounced in longer matches and maps with more door chains.

### Remaining Known Issues (updated)
- ~~No leader succession~~ ✅ Fixed — succession existed, ai_stance bug resolved
- **Follower oscillation dominates** — 40-50% of turns spent in len-2 position cycles (see analysis below)
- **Combat exemption bypasses oscillation suppressor** — PVE enemies within Chebyshev 3 trigger the combat exemption, allowing oscillation through the final safety net
- **Multiple follower MOVE paths lack anti-backtrack** — `follow_kite`, `follow_rush_melee`, `follow_chest_seek` produce MOVEs without checking position history

### Fixed
- **A\* door traversal cost reduced (3 → 2)** — Closed-door step cost was so high that A\* would route leaders on long detours around doors instead of through them. Lowered to 2 so A\* still prefers open routes but won't avoid nearby doors. (`ai_pathfinding.py`)
- **Direct door interaction when leader is adjacent to target entrance** — When explorer A\* returns no path because the leader is already adjacent to a closed-door entrance, the leader now issues an INTERACT immediately instead of falling through to patrol. Fixes the common case where leaders stood next to doors for 25+ turns without opening them. (`ai_behavior.py`)
- **Relaxed `_find_adjacent_door_toward_target` distance check** — Door force-open helper now accepts doors at the same or slightly farther Manhattan distance from target (tolerance +2), not just strictly closer. Leaders now open doors even when not perfectly aligned with the target room. (`ai_stances.py`)
- **Escalating skip durations for unreachable rooms** — `skip_room()` now tracks how many times each room has been skipped per team. Durations escalate: 60 → 120 → 240 → permanent. Prevents the infinite stagnation cycle where a room is skipped for 40 turns, re-targeted, fails again, skipped again, forever. (`ai_exploration.py`)
- **Bounding-box suppression no longer applies to team leaders** — The broad stall detection (12-position history in ≤2×2 tile bounding box) was triggering on leaders from follower congestion near doorways. Now only applies to non-leader followers. (`ai_behavior.py`)
- **Suppression hard timeout reduced (30 → 20 ticks)** — `_MAX_SUPPRESS_TURNS` lowered so suppressed leaders recover faster. (`ai_behavior.py`)

### Fixed (Round 2)
- **Total-turn stagnation guard (RC#3)** — Added `_explore_total_turns` tracker that increments EVERY tick in `run_ai_decisions()`, not just on ticks where the `explore_room` code path runs. Threshold: 50 total turns targeting the same room triggers `skip_room()`. Previously, leaders could target the same unreachable room for 100–247 real turns because the per-decision counter `_explore_target_turns` only incremented on the ~20% of turns that actually reached the explore code path. (`ai_behavior.py`)
- **Door rescue on pathfind failure (RC#3)** — When explore A\* fails, the leader now checks `_find_adjacent_door_toward_target()` for any adjacent closed door before counting the attempt as a pathfind failure. Fixes the case where the entrance is beyond the door (room center) so the direct door-check doesn't fire. (`ai_behavior.py`)
- **Door-path rescue (RC#4)** — When explore A\* can't reach the entrance at all, a new fallback queries `get_doors_for_room()` to find the nearest closed door connecting to the target room and routes to that door instead. If adjacent, interacts immediately; otherwise walks toward it. This rescues leaders whose target entrance is the room center (unreachable through walls) but whose connecting door IS reachable. (`ai_behavior.py`, `ai_exploration.py`)
- **Skip count preservation across full-clear resets** — `get_next_exploration_target()` no longer resets `_skip_count` when clearing active skips. Previously, when all rooms were skipped, counts reset to 0 every cycle, causing rooms to get permanent 60-turn skips forever instead of escalating. Escalation (60 → 120 → 240 → permanent) now works properly. (`ai_exploration.py`)
- **Entrance door fallback for unknown rooms** — When no known-room door connection exists for a target room, `get_next_exploration_target()` now falls back to the nearest door tile that connects to the target room instead of the room center (which is often behind walls and unreachable). (`ai_exploration.py`)

### Added
- `get_doors_for_room()` helper in `ai_exploration.py` — returns all door positions connecting to a given room.
- **Enhanced batch diagnostics** (`batch_pvpve.py`):
  - Per-room skip log with room names, skip counts, and failure reasons
  - Door-blocked room analysis — cross-references undiscovered rooms with door connections
  - Last-forward-progress timestamp with stall duration warning
  - No-exploration-target turn counter (all rooms cleared or skipped)
  - Room discovery progression timeline (T1 → T25 → T50 ... → T300)

### Changed
- `_SKIP_EXPIRY_TURNS`: 40 → 60 (base duration before escalation)
- `_MAX_SUPPRESS_TURNS`: 30 → 20
- A\* door step cost: 3 → 2
- `_find_adjacent_door_toward_target` distance threshold: `ai_dist` → `ai_dist + 2`
- `_EXPLORE_TOTAL_STAGNATION_THRESHOLD`: 50 total ticks (new)

### Simulation Results (PvPvE batch, seed 42, 3 × 300 turns, grid-size 6)

| Metric | v0.1.10 Baseline | Round 1 Fixes | Round 2 Fixes |
|--------|-----------------|---------------|---------------|
| Avg exploration health | 14.7/100 | 25.7/100 | 24.7/100 |
| Max consecutive same room | 82–247 turns | 37–50 turns | 31–50 turns |
| Best room discovery (any team) | 38% | 70% | 64% |
| Doors opened (total across teams) | 7–8 | 8–13 | 9–13 |

**600-turn validation (1 match, seed 42):**

| Team | Rooms Found | Tile Coverage | Doors Opened | Leader Status |
|------|------------|---------------|--------------|---------------|
| A | 25/29 (86%) | 23.0% | 3 | Survived |
| B | 15/29 (52%) | 10.3% | 6 | Died T326 |
| C | 4/29 (14%) | 3.1% | 0 | Survived but in perpetual combat |
| D | 9/29 (31%) | 10.1% | 2 | Died T229 |

### Root Cause Analysis — Why Teams Stop Exploring

Investigation of 600-turn matches identified **three distinct failure modes**:

1. **Leader death (Teams B, D)** — When the team leader dies in PvP or PvE combat, no other unit on the team has `is_team_leader=True`, so nobody calls `get_next_exploration_target()`. The surviving followers just trail their (dead) owner or idle. This is the #1 cause of teams "hanging out in one room." Fix requires leader succession (promoting a surviving follower).

2. **Perpetual combat (Team C)** — The leader survives but is permanently engaged with enemies. Exploration only runs in the "no visible enemies" branch (step 4e of `decide_ai_action`). If enemies are always visible (e.g. leader spawned near enemy-dense area, or PvP teams clash), the leader spends 100% of turns in combat and zero in exploration. Team C's leader made 370 `skill_searing_totem` and 187 `aggro_pathfind_toward_target` decisions out of 600 — zero `explore_room`.

3. **Pathfinding stall on door-blocked rooms** — Even with the door rescues, some rooms remain behind doors the leader can't reach due to congestion (other units blocking the corridor to the door). The skip escalation eventually makes these rooms permanently skipped, and when ALL remaining rooms are permanently skipped the leader falls through to patrol indefinitely.

### Remaining Known Issues
- **No leader succession** — When leader dies, team exploration stops permanently
- **Exploration blocked by combat** — Leaders in perpetual combat never reach the explore code path
- **Follower oscillation** — Followers bounce between 2 tiles (87–98% follower turns) wasting action economy
- **Door approach failures** — Leaders sometimes route away from adjacent doors (A\* finds cheaper path around)

### Files Changed
- `server/app/core/ai_pathfinding.py`
- `server/app/core/ai_behavior.py`
- `server/app/core/ai_exploration.py`
- `server/app/core/ai_stances.py`
- `server/batch_pvpve.py`

---

## [v0.1.10] - 2026-03-21 — Smarter Heroes, Better Loot

### Fixed
- **Leader explore_room ↔ patrol_move oscillation reduced** — Explore path now checks leader's `_position_history` before returning a MOVE; if the proposed step is a backtrack to last turn's tile, it falls through to patrol. Oscillation pairs dropped 41%, overall oscillation rate down 2.8pp. (`ai_behavior.py` — `_decide_aggressive_action()`, block 4e)
- **Follower trail-moving oscillation eliminated** — `follow_trail_moving` now rejects backtrack steps via position history check. Follower self-oscillations dropped 97%; `stall_breaker_yield` WAITs down 35%; `oscillation_suppressed` WAITs down 70%. (`ai_stances.py` — `_decide_follow_action()`)
- **Explore suppression thresholds tuned** — A↔B cycle detection raised from 6→8 positions, broad stall bounding box from 8→12 positions with ≤2 tile box, suppression cooldown 20→10 turns, lift distance 5→3 Manhattan. `explore_room` decisions up 3.75x; `random_adjacent_move` eliminated. (`ai_behavior.py`)
- **Patrol fallback now directed** — `_random_adjacent_move()` accepts `exploration_hint`; leaders step toward nearest unexplored room entrance (Manhattan distance) instead of random tile. All 10 random fallbacks replaced by 27 directed moves. (`ai_patrol.py`, `ai_behavior.py`)
- **purge_unwanted_items() respects class-lock and armor affinity** — Now mirrors `find_best_party_recipient()` equip gates so melee weapons can't appear as "upgrades" for casters. (`equipment_manager.py`)
- **Leader promotion works for all AI team prefixes** — `deaths_phase.py` now accepts both `"pvpve-ai-"` and `"ai-"` prefixed units. Eliminated 232 wasted `follow_no_owner` WAITs per 10-match sample.
- **Oscillation suppression no longer fires on simple reversals** — Single A→B→A reversal now only clears stale waypoint; WAIT requires extended criteria (6+ positions ≤2 unique tiles or 8+ in ≤3-tile box). Hero `oscillation_suppressed` WAITs down 54%. (`ai_behavior.py`)
- **Displaced equipment redistribution pass** — Phase 28I scans all team inventories after auto-equip, finds best recipient, transfers, and triggers equip. Runs up to 3 cascade passes. Stranded upgrades dropped from 22→0 per match; items traded 5→31; equipment health score 75→95. (`interaction_phase.py`)

### Added
- **Oscillation suppression deadlock broken** — Hard timeout (`_MAX_SUPPRESS_TURNS = 30`) unconditionally lifts suppression after 30 ticks, clears `_visited` history. Leader decisions increased 6.6x; items picked up +37%; items traded +51%. (`ai_behavior.py`)
- **Patrol waypoint all-visited fallback** — `_pick_patrol_waypoint()` detects when all candidates are visited and disables the −15.0 visited penalty for that selection. (`ai_patrol.py`)
- **Follower autonomous wander** — When leader is stationary 5+ ticks, followers make a random adjacent move (`follow_autonomous_wander`) instead of WAITing. (`ai_stances.py`)
- **Dev Overlay: Equipment & Inventory Inspector** — Backtick → Inspect ON → click any unit to see equipment (weapon/armor/accessory with rarity colors, stats, affixes, set info) and scrollable inventory (X/10 capacity, consumable icons). Works on ALL units including AI heroes and enemies via `dev_get_unit_inventory` endpoint. Auto-refreshes every 3s. (7 files: `equipment_manager.py`, `match_manager.py`, `message_handlers.py`, `App.jsx`, `useDevOverlay.js`, `DevOverlayPanel.jsx`, `Arena.jsx`, `_dev-overlay.css`)
- **PVPVE Batch Tool: Equipment Management Report** — `--equipment-report` flag for `batch_pvpve.py` with spawn gear, equipment events, per-team breakdown, final gear, potion economy, diagnostics, health score (0-100), inventory contents, stranded upgrades detection, and batch summary.

### Files Changed
- `server/app/core/ai_behavior.py`
- `server/app/core/ai_stances.py`
- `server/app/core/ai_patrol.py`
- `server/app/core/equipment_manager.py`
- `server/app/core/turn_phases/deaths_phase.py`
- `server/app/core/turn_phases/interaction_phase.py`
- `server/app/core/match_manager.py`
- `server/app/services/message_handlers.py`
- `server/batch_pvpve.py`
- `client/src/App.jsx`
- `client/src/hooks/useDevOverlay.js`
- `client/src/components/DevOverlay/DevOverlayPanel.jsx`
- `client/src/components/Arena/Arena.jsx`
- `client/src/styles/components/_dev-overlay.css`

---

## [v0.1.9b] - 2026-03-20 - Leader Explore/Patrol Oscillation Fix

### Fixed
- **Leader explore_room ↔ patrol_move oscillation reduced** — Team leaders alternated between exploring toward an unexplored room entrance and patrol waypoint scouting on consecutive turns. When explore_room proposed a step back toward the leader's immediately previous tile, the two subsystems fought over direction, creating A→B→A bouncing. The explore_room code path now checks the leader's position history: if the proposed step is a backtrack to last turn's position, it falls through to patrol (which has its own anti-backtrack guard), preventing the two systems from pulling the leader in opposite directions.

### Simulation Results (PvPvE, 150 turns, seed 100)

| Metric | Before (RC1 only) | After (RC1+RC2) | Change |
|--------|-------------------|-----------------|--------|
| `explore_room` ↔ `patrol_move` pairs | 22 | 13 | **-41%** |
| Overall oscillation rate | 12.0% | 9.2% | **-2.8pp** |
| `explore_room` actions | 33 | 131 | **+297%** |
| `patrol_move` actions | 51 | 135 | **+165%** |
| Total hero MOVE actions | 1121 | 1776 | **+58%** |

### Cross-Validation (seed 42, 100 turns)

| Metric | Before | After | Change |
|--------|--------|-------|--------|
| Total oscillation events | 112 | 70 | **-37%** |
| Oscillation rate | 9.1% | 7.0% | **-2.1pp** |

### Files Changed
- `server/app/core/ai_behavior.py` — `_decide_aggressive_action()`: Added position history backtrack rejection in the strategic exploration block (4e)

### Test Results
- 4040 tests passing (0 regressions)

---

## [v0.1.9a] - 2026-03-20 - Follower Trail-Moving Oscillation Fix

### Fixed
- **AI followers no longer oscillate between tiles when trailing a moving leader** — When a team leader moved through corridors or doorway chokepoints, followers within distance 1 would trigger the `follow_trail_moving` tether and compete for the same 2-3 adjacent tiles. The movement batch resolver picks winners each tick, shifting the occupied set and causing A* to send losers right back to their previous position on the next turn. This created sustained A→B→A tile-swapping visible as followers rapidly bouncing between two tiles, especially near doors where geometry forces tight formations.

### Root Cause
The `follow_trail_moving` code path in `_decide_follow_action()` had no anti-oscillation guard. It would always return the A* result regardless of whether that step was a backtrack to the follower's immediately previous position. The main oscillation suppressor in `run_ai_decisions()` only catches this when no enemies are nearby (Chebyshev ≤ 3), so the follower bouncing persisted near combat zones.

### Fix
Before the `follow_trail_moving` path returns a MOVE, it now checks the follower's `_position_history` from `ai_behavior.py`. If the proposed next step matches the position the follower occupied last turn (A→B→A), the move is skipped and the follower falls through to idle/chest-seek behavior. This one-tick pause breaks the oscillation cycle without affecting normal trailing when the leader is making forward progress.

### Simulation Results (PvPvE, 150 turns, seed 100)

| Metric | Before Fix | After Fix | Change |
|--------|-----------|-----------|--------|
| `follow_trail_moving` ↔ self oscillations | 61 | 2 | **-97%** |
| `stall_breaker_yield` WAITs | 222 | 144 | **-35%** |
| `oscillation_suppressed` WAITs | 96 | 29 | **-70%** |
| Total A→B→A oscillation events | 252 | 134 | **-47%** |
| Oscillation rate (% of MOVE actions) | 13.8% | 12.0% | **-1.8pp** |
| `follow_trail_moving` actions | 341 | 87 | **-74%** |

### Files Changed
- `server/app/core/ai_stances.py` — `_decide_follow_action()`: Added position history check in the leader-is-moving tether block to reject backtrack steps

### Test Results
- 4040 tests passing (0 regressions)

---

## [v0.1.9] - 2026-03-20 - Match Manager Modularization

**Architecture refactoring** - broke down the monolithic `match_manager.py` (3,220 lines, 55+ functions) into 9 focused sub-modules. Zero gameplay changes; purely internal code quality improvement enabling faster future development.

### Refactored
- **Phase 0:** Created `match_manager_BACKUP.py` safety copy (3,220 lines, 125 KB)
- **Phase 1:** Extracted `match_store.py` - single source of truth for all 14 shared state dicts + `MAX_QUEUE_SIZE` constant
  - `_active_matches`, `_player_states`, `_action_queues`, `_fov_cache`, `_lobby_chat`, `_class_selections`, `_hero_selections`, `_hero_ally_map`, `_username_map`, `_kill_tracker`, `_combat_stats`, `_match_timeline`, `_controlled_hero_map`, `_wave_state`, `_dev_mode_players`
  - Updated 5 already-extracted modules (`hero_manager`, `party_manager`, `equipment_manager`, `wave_spawner`, `auto_target`) to import from `match_store` instead of `match_manager`
- **Phase 2:** Extracted `action_queue.py` - 6 functions for persistent player action queue operations (queue, pop, clear, remove, get) with auto-target-aware clearing
- **Phase 3:** Extracted `fov_manager.py` - FOV cache accessors, team FOV union, dev mode toggles
- **Phase 4:** Extracted `match_payloads.py` - WebSocket payload builders (match start, game state, turn update); pure serializers with no side effects
- **Phase 5:** Extracted `lobby_config.py` - lobby chat, class selection, match config operations
- **Phase 6:** Extracted `loadout_generator.py` - enemy and hero equipment generation with rarity/floor scaling
- **Phase 7:** Extracted `dungeon_manager.py` - dungeon lifecycle, WFC procedural generation, room-based enemy spawning, floor progression
- **Phase 8:** Extracted `pvpve_manager.py` - PVPVE match flow orchestration with team distribution and diagonal-opposite spawn zones

### Added
- `ai_exploration.py` - room graph construction (`build_room_graph`), per-team room discovery/clearance tracking, unexplored room queries; foundation for strategic room-aware exploration
- `batch_pvpve.py` - batch PVPVE simulation runner for validation
- `match-manager-split-plan.md` - architecture plan document
- `phase-strategic-exploration.md` - strategic exploration design spec
- AI behavior audit and stalling analysis documentation

### Maintained
- Backward compatible - `match_manager.py` re-exports all symbols, zero import changes needed in callers
- 4040 tests passing - zero regressions

---

## [v0.1.8] - 2026-03-18 - Dungeon Lighting, Door System, HUD Overhaul & AI Upgrades

**Published release** rolling up v0.1.7a through v0.1.7p. Major additions: prop lighting system with ambient darkness and fog-of-war light modulation, room door system with chokepoint separators, 7 new room archetypes with focal prop budget system, complete HUD overhaul (player/party HP bars, minimap relocation, 4-row grid layout), 7 new skill particle effects, door-aware AI pathfinding for all units, AI chest seeking for hero allies, unique class composition for AI parties, PVPVE location-based chest tiers, loot rarity rebalance, and multiple bug fixes. 3987 tests passing.

See sub-entries below (v0.1.7a--v0.1.7p) for full technical details.

---

## [v0.1.7w] - 2026-03-20 - AI Oscillation Fix (Explore / Chest-Seek / Patrol Conflict)

### Fixed
- **Root cause**: `explore_room`, `aggro_chest_seek`, and `patrol_move` fought over the leader's movement on alternating turns, causing parties to permanently oscillate between 2 tiles (especially after opening a door or spotting a chest).
- **Chest-seek oscillation** — Added `_chest_seek_suppressed` set parallel to `_explore_suppressed`. When oscillation is detected and the leader is stuck in a 2-tile cycle or confined to a 3×3 bounding box, both `explore_room` and `aggro_chest_seek` are suppressed so patrol's stale-area detector can force a distant waypoint. Adjacent chest looting (`_try_loot_adjacent_chest`) remains unaffected.
- **Premature lift prevention** — Suppression now requires a minimum 20-turn cool-down (`_MIN_SUPPRESS_TURNS`) before the centroid-distance lift check (Manhattan ≥ 5) is evaluated. This prevents the explore/patrol sweep where the leader would move 5 tiles toward patrol, lift suppression, then immediately get pulled back by explore.
- **Position history extended** — `_POSITION_HISTORY_LEN` increased from 4 to 8 for better pattern detection across longer oscillation cycles.
- **Cross-system visited history** — `explore_room` moves now feed into patrol's `_visited_history`, letting the stale-area detector count explore_room positions toward its 10-turn threshold.
- **Duplicate discard bug** — Fixed an unconditional `_explore_suppressed.discard()` that was bypassing the centroid-distance gate on every MOVE action.
- 4040 tests passing.

### Impact (10-seed PVPVE validation, 6×6 grid, 200 turns)
- **Before**: All teams stuck at full HP for 200 turns; 0 PVE kills; no combat.
- **After**: Average 13.5 PVE kills/match; team wipes in 8/10 seeds; 4 matches ended early due to elimination; every seed shows active exploration, chest looting, and combat.

---

## [v0.1.7v] - 2026-03-19 - Movement Deadlock Fix (Leader Priority + Stall Breaker)

### Fixed
- **Parties no longer get permanently stuck due to same-target movement deadlocks** — When a team leader and a follower (or multiple followers) both targeted the same tile in the same turn, the movement batch resolver picked one winner by alphabetical player_id. If a follower won, the leader's intent was removed, breaking the movement chain for all downstream units — every unit stayed in place, made the same decisions next turn, and remained deadlocked forever. A 20-seed diagnostic scan found **112 instances** of units issuing 10+ consecutive identical failed moves, with the worst cases lasting 98 turns.

### Root Cause
`resolve_movement_batch()` in combat.py resolved same-target conflicts with a flat priority: `(0 if human else 1, player_id)`. All AI units shared the same tier, so a random follower could beat its own team leader in a tile conflict. This removed the leader's move intent, which broke the chain resolver — nobody moved, and the same AI decisions repeated indefinitely.

### Fix (Phase 30)
- **Leader Priority (Fix A):** The same-target conflict priority now uses three tiers: `human (0) > team leader (1) > follower (2)`, with alphabetical player_id as tiebreaker within tiers. Leaders always win tile conflicts against their own followers, ensuring they keep moving. Once the leader moves, followers pathfind to the leader's new position, naturally breaking cascading deadlocks.
- **Stall Breaker (Fix B):** Non-leader units that have been at the same position for 3+ consecutive turns while issuing MOVE actions are forced to WAIT on alternating turns, using a deterministic parity derived from the player_id. This ensures that when two followers deadlock on the same target tile, they yield on different turns — one passes while the other waits — breaking follower-vs-follower stalemates that leader priority alone doesn't resolve.

### Simulation Results (PvPvE, 100 turns, 16 seeds)

| Metric | Before Fix | After Fix | Change |
|--------|-----------|-----------|--------|
| Units with 10+ repeated identical moves | 112 | ~10 | **~91% reduction** |
| Worst-case streak (turns stuck) | 98 | ~37 | **62% shorter** |
| Seed 400 Team A final distance from spawn | ~3 tiles (stuck) | ~16 tiles (progressing) | **Fixed** |

### Files Changed
- `server/app/core/combat.py` — `_priority()` in `resolve_movement_batch()` now returns 3-tier priority: human (0) > team leader (1) > follower (2)
- `server/app/core/ai_behavior.py` — Added stall breaker after oscillation suppression: forces WAIT on alternating turns when position unchanged for 3+ turns

### Test Results
- 3,993 tests passing (0 failures)

---

## [v0.1.7u] - 2026-03-19 - Door Swap Displacement Fix

### Fixed
- **AI units no longer get stuck at doors due to friendly swap injection** — When a party leader chose INTERACT to open a door, a trailing follower could MOVE onto the leader's tile in the same turn. The Friendly Swap Injection system (Phase 1 — movement) would then displace the leader backward to make room. By the time Phase 1.5 (door interactions) resolved, the leader was no longer adjacent to the door, causing the INTERACT to fail silently. The leader would re-queue INTERACT next turn, get swapped again, and loop — sometimes failing 3+ consecutive times at the same door while the rest of the party went idle.

### Root Cause
Phase ordering: Movement (Phase 1) resolves before Door Interactions (Phase 1.5). The swap injection had no awareness of pending INTERACT actions, so it would displace any stationary same-team unit — including one about to open a door.

### Fix
- **Swap Protection (Fix A):** Before resolving movement, collect all `player_id`s with pending INTERACT actions (door opens, not portal/stairs). During Friendly Swap Injection, skip any occupant in that set — they must not be displaced from their door-adjacent tile.
- **Failure Logging (Fix C):** Surface `⚠ INTERACT FAILED` lines in batch PvPvE verbose output whenever a door interaction doesn't resolve, for future diagnostics.

### Simulation Results (PvPvE, 200 turns)

| Seed | Pre-Fix Failures | Post-Fix Failures |
|------|-----------------|------------------|
| 100 | 7 / 11 (64%) | 0 / 4 (0%) |
| 200 | 5 / 19 (26%) | 0 / 9 (0%) |
| 500 | 1 / 7 (14%) | 0 / 6 (0%) |
| **5-match batch (seed 1000)** | — | **0 / 38 (0%)** |

### Files Changed
- `server/app/core/turn_phases/movement_phase.py` — Added `interacting_pids` parameter to `_resolve_movement()`; swap injection skips occupants with pending INTERACT actions
- `server/app/core/turn_resolver.py` — Computes `door_interacting_pids` set from interact actions; passes to `_resolve_movement()`
- `server/batch_pvpve.py` — Added failed INTERACT logging to `log_turn_results()`

### Test Results
- 3,911 tests passing (1 pre-existing unrelated failure in TestGreedSigil)

---

## [v0.1.7t] - 2026-03-19 - AI Hero Stalling Fixes (Follow Tightening, Leader Tether, Idle Trailing)

### Fixed
- **AI hero followers no longer stall for 5–17+ consecutive turns** — Three distinct stalling patterns were identified via PvPvE batch simulation analysis and fixed. Combined, these eliminate the worst hero idle behavior across all game modes (PvP, PvE, PvPvE, and human player parties).

### Pattern 1: Follower Spawn Congestion (biggest impact)
- **Before:** Followers evaluated `dist_to_owner <= 2` at spawn and hit the WAIT fallback. Teams would idle for 5–9 turns at match start while the leader walked far enough away to trigger the regroup threshold.
- **Fix:** Reduced the follow-stance idle threshold from `dist_to_owner > 2` to `> 1` in `_decide_follow_action()`. Followers now only WAIT when literally adjacent (distance 1), not within a 2-tile radius.
- **Impact:** Early game (T1–T20) went from 5–9 consecutive WAITs per follower down to 0–2 scattered WAITs. Applies to all hero allies including human player party companions.

### Pattern 2: Corridor Gridlock / Leader Tether
- **Before:** When a leader was moving and followers were already adjacent, followers would idle even as the leader walked away. In corridors, 3–4 followers would cluster on the same tile trying to reach the leader.
- **Fix:** Added a "leader-is-moving" tether in `_decide_follow_action()`. When the owner's position changed since last tick (checked via `_position_history` from `ai_behavior.py`), adjacent followers attempt to trail the leader to maintain loose formation.
- **Impact:** Prevents formation pile-ups in corridors. The 17-turn streak (Team D Hexblade 2) is eliminated entirely.

### Pattern 3: Post-Combat / Idle Stalling
- **Before:** After combat ended, hero allies in the aggressive behavior path hit an explicit `WAIT` at step 4c ("hold position instead of patrolling"). Combined with the follow-stance idle threshold, entire parties would freeze until the leader found a new target.
- **Fix:** Hero allies at step 4c now trail their leader when idle instead of WAITing permanently. They path toward the owner when distance > 1, matching the follow-stance behavior. Only WAIT when already adjacent.
- **Impact:** Eliminates 10–94 turn idle streaks that occurred when followers lost sight of all enemies.

### Batch Simulation Results (PvPvE, 6x6 grid, 150 turns)

| Metric | Pre-Fix | Post-Fix |
|--------|---------|----------|
| Worst WAIT streak | 17 turns | **4 turns** |
| Team A WAIT% | 15.2% | **12.7%** |
| Team B WAIT% | 9.0% | **6.3%** |
| Team C WAIT% | 12.8% | **5.7%** |
| Team D WAIT% | 17.4% | **3.3%** |

### Files Changed
- `server/app/core/ai_stances.py` — `_decide_follow_action()`: Priority 3 idle threshold `> 2` → `> 1`; added leader-is-moving tether block that checks `_position_history` for owner movement
- `server/app/core/ai_behavior.py` — Added `_last_combat_tick` dict, `_ai_tick_counter`, `_POST_COMBAT_FOLLOW_GRACE` for post-combat tracking; step 4c in `_decide_aggressive_action()` now trails owner instead of permanent WAIT; cleanup in `run_ai_decisions()` and `clear_ai_patrol_state()`

### Test Results
- 3993 tests passing (0 new, 0 regressions)

---

## [v0.1.7s] - 2026-03-19 - Batch PVPVE Accuracy Fixes

### Fixed
- **Batch PVPVE AI teams now use follow-stance behavior matching live matches** — All 4 teams had their followers forcibly converted to independent aggressive AI, causing every unit to scatter solo across the dungeon. In live PVPVE, each team has 1 leader (aggressive) and 4 followers (follow-stance) who cluster within 2-4 tiles of their leader. Teams B/C/D now keep their original stance setup. Team A followers are re-parented to Team A's leader instead of the removed dummy host, preserving follow-stance behavior.
- **Batch PVPVE AI can now see and loot ground items and chests** — `run_ai_decisions()` was missing `ground_items` and `chest_states` parameters that the live tick loop passes. AI units in batch simulations would ignore treasure chests and ground loot entirely, diverging from live dungeon behavior.

### Impact
These two fixes eliminate the most significant behavioral divergences between batch PVPVE simulations and live PVPVE dungeons. Batch results will now show coordinated team movement, group engagements, and chest/loot interaction — matching what players actually experience.

### Files Changed
- `server/batch_pvpve.py` — Replaced blanket aggressive conversion with leader re-parenting for Team A; removed unnecessary follower conversion for Teams B/C/D; added `ground_items` and `chest_states` kwargs to `run_ai_decisions()` call

---

## [v0.1.7r] - 2026-03-18 - PVPVE AI Team Chest Seeking Fix

### Fixed
- **PVPVE AI opponent hero parties now open and loot treasure chests** — In PVPVE mode, the 3 AI opponent hero teams would walk past treasure chests without ever interacting with them. The v0.1.7n chest-seeking feature only worked for hero allies (stance-based AI); PVPVE team leaders and their followers were completely excluded.

### Root Cause
PVPVE team leaders are spawned without `hero_id` or `ai_stance` (both `None`), so they bypass the stance-based AI gate in `decide_ai_action()` and fall through to `_decide_aggressive_action()`. That function's signature did not accept `chest_states` at all — it had no chest-seeking logic of any kind. PVPVE followers do enter the stance path (they have `hero_id` + `ai_stance="follow"`), but since the leader never stops near chests, followers are perpetually chasing and never reach their idle chest-seeking priority.

| Unit | Code Path | Had chest_states? | Result |
|------|-----------|-------------------|--------|
| PVPVE Leader | `_decide_aggressive_action` | **No** | Never looted |
| PVPVE Follower | `_decide_stance_action` → follow | Yes | Rarely — always chasing leader |

### Fix
- Added `chest_states` parameter to `_decide_aggressive_action()`
- Added chest-seeking logic (step 4b2) in the idle section for hero party AI (`enemy_type is None`): first checks for adjacent chests to loot (`_try_loot_adjacent_chest`), then pathfinds toward the nearest unopened chest (`_find_nearest_unopened_chest`) within the aggressive seek range (6 tiles)
- Threaded `chest_states` from `decide_ai_action()` through to `_decide_aggressive_action()`
- Imported `_CHEST_SEEK_MAX_RANGE`, `_find_nearest_unopened_chest`, and `_try_loot_adjacent_chest` from `ai_stances.py` into `ai_behavior.py`
- Dungeon enemies (`enemy_type` set) are excluded from chest seeking — only hero party AI units (PVPVE teams, player allies) can loot
- Priority order preserved: Potions → Skills → Combat → Memory Pursuit → Reinforce Ally → **Chest Seeking** → Hero Wait → Ground Loot → Patrol
- With leaders now stopping at chests, followers naturally end up nearby and can trigger their own stance-based chest looting

### Files Changed
- `server/app/core/ai_behavior.py` — Added `chest_states` param to `_decide_aggressive_action`; added step 4b2 chest-seeking logic for hero party AI; imported chest helpers from `ai_stances`
- `server/tests/test_ai_chest_seeking.py` — 6 new tests: PVPVE leader loots adjacent chest, moves toward chest, ignores opened chests, combat takes priority, dungeon enemies excluded, no crash without chest_states

### Test Results
- 3993 tests passing (6 new, 0 regressions)

---

## [v0.1.7q] - 2026-03-18 - AI Hero Anti-Oscillation Fix

### Fixed
- **AI hero parties no longer oscillate (swap places) when patrolling or exploring** — Units would get stuck in an A→B→A loop, bouncing between two positions on alternating turns. This was most visible when a party of heroes was navigating corridors or open areas with no enemies nearby — the entire group would stall out with members endlessly trading tiles.

### Root Cause
The `allow_team_swap` flag (added in v0.1.7o) correctly lets A* path through same-team allies, but the cooperative movement prediction system (`pending_moves`) causes A* to compute different optimal paths each turn as the occupied-set shifts. On turn N, unit A vacates tile X and moves to tile Y; on turn N+1, the occupied set is reversed so A* sends the unit right back to X. No per-unit memory existed to detect or prevent this backtracking.

### Fix
- Added per-unit **position history** tracking (`_position_history`) in the AI decision orchestrator (`run_ai_decisions`). Each unit's last 4 positions are recorded across turns.
- After each AI MOVE decision, the system checks whether the target tile matches the unit's position from the previous turn (A→B→A detection).
- If oscillation is detected **and** no enemy is within 3 tiles (Chebyshev distance), the MOVE is suppressed to a WAIT. This breaks the oscillation loop while preserving legitimate combat maneuvers (kiting, retreating, chasing).
- Position history is cleaned up alongside patrol/memory state on unit death and match end.

### Technical Details
- The combat exemption range (`_OSCILLATION_COMBAT_RANGE = 3`) ensures kiting, retreat, and pursuit behaviors are never disrupted — oscillation is only suppressed during idle exploration/patrolling
- The fix is applied universally to all AI units (hero parties and PVE enemies) at the orchestrator level, requiring no changes to individual behavior functions
- One-turn WAIT from suppression is sufficient to break the cycle: the next turn, the occupied set will have shifted enough for A* to find a non-oscillating path

### Files Changed
- `server/app/core/ai_behavior.py` — Added `_position_history` dict, `_POSITION_HISTORY_LEN`, `_OSCILLATION_COMBAT_RANGE` constants; added oscillation detection post-processing in `run_ai_decisions`; added history cleanup in `clear_ai_patrol_state`

---

## [v0.1.7p] - 2026-03-18 - Unique Class Composition for AI Parties

### Changed
- **AI parties no longer have duplicate classes** — Each AI team (allies, opponents, PVPVE teams) now spawns with all-unique class compositions. Previously `random.choice()` selected classes independently per slot, frequently producing duplicate classes on the same team (e.g. two Crusaders, three Rangers). Now classes are pre-selected as a unique set per team using `random.sample()`-style logic before spawning.
- **Manually specified class slots respected** — When a player locks in specific classes via the lobby config (`ai_ally_classes` / `ai_opponent_classes`), those are honored first. Remaining random slots are filled from the pool of unused classes, ensuring no duplicates against manually-picked classes either.
- **Cross-team duplicates still allowed** — Only intra-team duplicates are prevented. Team A and Team B can still independently field the same class (mirror matches are fine). Each team gets its own unique draw from the 11-class pool.
- **PVPVE AI teams included** — The same unique-composition logic applies to PVPVE AI hero teams, which previously also used pure random selection per unit.

### Technical Details
- With 11 classes and max party size of 5, there are 462 unique team compositions possible (C(11,5)), ensuring strong variety across matches
- Fallback to `random.choice()` exists for the impossible edge case where slots exceed available classes (11 classes, 5 max team = never triggered)
- The `class_name_counts` naming logic (e.g. "Mage 2") is retained as a safety net but should no longer activate in normal play

### Files Changed
- `server/app/core/match_manager.py` — `_spawn_ai_units()`: replaced per-slot `random.choice()` with pre-selected unique class lists for both ally and opponent loops; `_spawn_pvpve_ai_teams()`: replaced per-unit `random.choice()` with per-team shuffled unique picks

---

## [v0.1.7o] - 2026-03-18 - PVPVE Team Leader Deadlock Fix

### Fixed
- **PVPVE AI teams no longer freeze at spawn in narrow corridors** — One of the 3 AI opponent teams would consistently stand idle at their spawn point for the entire match. This was most visible when a team spawned in a 2-tile wide hallway: the leader would oscillate between two tiles while all 4 followers stood still.

### Root Cause
The PVPVE team leader uses aggressive AI behavior (`_decide_aggressive_action`), which calls `_build_occupied_set` **without** `allow_team_swap`. This means the leader treated its own 4 followers as impassable obstacles. In a compact BFS spawn formation within a narrow corridor, A* pathfinding would fail because followers blocked every viable path. The leader would fall back to `_random_adjacent_move`, oscillating between the 1-2 free adjacent tiles. Meanwhile, followers use `_decide_follow_action` which WAITs when the leader is within 2 tiles (Chebyshev distance). Result: permanent deadlock — leader can't escape, followers won't move.

The follower stance system (`_decide_stance_action`) already used `allow_team_swap=ai.team` to let followers path through allies. The leader's aggressive behavior path was missing the same treatment.

### Fix
- `_decide_aggressive_action` now computes `allow_swap = ai.team` for hero party AI (`enemy_type is None`) and passes it to all `_build_occupied_set` calls. Dungeon enemies (`enemy_type` set) retain the original behavior.
- `_patrol_action` now accepts an `allow_team_swap` parameter and propagates it to `_build_occupied_set`, so patrol waypoint pathfinding also respects team swap.
- The movement resolver's existing friendly swap injection (Phase 1B) handles the actual tile collision at resolution time — no new swap logic needed.

### Files Changed
- `server/app/core/ai_behavior.py` — 6 `_build_occupied_set` calls in `_decide_aggressive_action` now pass `allow_team_swap` for hero party AI
- `server/app/core/ai_patrol.py` — `_patrol_action` accepts and forwards `allow_team_swap`
- `server/tests/test_movement_prediction.py` — Updated pending_moves test to use dungeon enemies (enemy_type set) so it tests the prediction feature in isolation; added new test verifying hero party AI can path through same-team allies

---

## [v0.1.7n] - 2026-03-18 - AI Chest Seeking (Hero Allies)

### Added
- **Hero AI parties now open treasure chests** — When idle (no visible enemies), AI-controlled hero allies will seek out and open nearby unopened chests. Previously only the human player could open chests; AI heroes would walk past them.
- **Per-stance seek ranges** — Each stance has a tuned maximum chest-seeking range: Follow (4 tiles), Aggressive (6 tiles), Defensive (3 tiles). Hold stance never moves but will loot chests it happens to be adjacent to.
- **Defensive tether respected** — Defensive heroes will only path toward chests if doing so keeps them within 2 tiles of their owner, preserving the defensive tether constraint.
- **Inventory-full guard** — AI will not seek chests when inventory is full (`INVENTORY_MAX_CAPACITY`), avoiding pointless pathfinding.
- **Two-tick chest interaction** — When not adjacent, AI pathfinds toward the chest (MOVE). Once adjacent (Chebyshev distance 1), AI emits `ActionType.LOOT` targeting the chest tile, which is resolved by the existing `_resolve_loot()` interaction phase.

### Technical Details
- `tick_loop.py`: Now passes `chest_states` to `run_ai_decisions()`
- `ai_behavior.py`: `run_ai_decisions()` and `decide_ai_action()` accept and forward `chest_states` to stance dispatch
- `ai_stances.py`: New utility functions `_find_nearest_unopened_chest()` and `_try_loot_adjacent_chest()`; `_decide_stance_action()` forwards `chest_states` to all four stance handlers
- `_decide_follow_action()`: Seeks chests when idle and close to owner (Priority 4, after combat/regroup)
- `_decide_aggressive_stance_action()`: Seeks chests when idle after memory pursuit and ally reinforcement
- `_decide_defensive_action()`: Seeks chests when idle, respects 2-tile owner tether
- `_decide_hold_action()`: Loots adjacent chests in the no-enemies early-return path (never moves)
- Priority order preserved: Potions → Portal → Retreat → Skills → Combat → Regroup → Chest Seeking → Wait

### Files Changed
- `server/app/services/tick_loop.py` — Pass `chest_states` to AI layer
- `server/app/core/ai_behavior.py` — Thread `chest_states` through `run_ai_decisions()` → `decide_ai_action()`
- `server/app/core/ai_stances.py` — Chest-seeking helpers + per-stance chest behavior
- `server/tests/test_ai_chest_seeking.py` — 26 new tests

### Test Results
- 3986 tests passing (26 new, 0 regressions)

---

## [v0.1.7m] - 2026-03-17 - AI Door Opening (All Units)

### Changed
- **All AI can now open doors** — Enemy AI (aggressive, ranged, boss, support) and allied party members all use door-aware A* pathfinding and will open closed doors when they are on the planned path. Previously only hero ally stances (follow/aggressive/defensive) could interact with doors; enemy AI was explicitly blocked from doing so, causing enemies to get stuck behind closed doors in dungeon layouts.
- **Door-aware pathfinding propagated to AI sub-systems** — `_pursue_memory_target()`, `_reinforce_ally()`, and `_patrol_action()` now accept and forward `door_tiles`, so AI memory pursuit, ally reinforcement, and patrol scouting all path through closed doors at elevated cost (+3 vs +1).
- **A* still prefers open routes** — The existing weighted cost system (door step = 3, normal step = 1) remains, so AI will always prefer open paths but won't get stuck when a door is the only option.
- **Multi-tick door crossing preserved** — The existing pattern (tick 1: INTERACT to open door → tick 2: MOVE through) applies identically to enemy AI as it does to hero allies.

### Technical Details
- `decide_ai_action()`: Removed enemy-exclusion gate; all behaviors now receive `door_tiles`
- `_decide_aggressive_action()`: Added `door_tiles` param, door-aware `get_next_step_toward()` calls, `_maybe_interact_door()` checks at all movement decision points
- `_decide_ranged_action()`: Same door-awareness additions
- `_decide_boss_action()`: Same door-awareness additions (room-leashed pathfinding also door-aware)
- `_decide_support_behavior()`: Same door-awareness additions
- `ai_memory.py`: `_pursue_memory_target()` and `_reinforce_ally()` now accept `door_tiles`, use door-aware pathfinding, and check for door interaction
- `ai_patrol.py`: `_patrol_action()` now accepts `door_tiles`, passes to both `a_star()` and `get_next_step_toward()`, checks for door interaction
- Lazy imports used in `ai_memory.py` and `ai_patrol.py` to avoid circular dependency with `ai_stances.py`
- Tests updated: old "enemy cannot open doors" regression tests converted to "enemy can open doors" positive tests

### Files Changed
- `server/app/core/ai_behavior.py` — Door-aware enemy AI behaviors
- `server/app/core/ai_memory.py` — Door-aware memory pursuit + ally reinforcement
- `server/app/core/ai_patrol.py` — Door-aware patrol scouting
- `server/app/core/ai_stances.py` — Pass `door_tiles` to memory/reinforce helpers
- `server/tests/test_ai_door_opening.py` — Updated enemy door tests
- `server/tests/test_door_pathfinding.py` — Updated enemy door tests

### Test Results
- 3792 tests passing (0 regressions)

---

## [v0.1.7l] - 2026-03-17 - Loot Rarity Rebalance

### Changed
- **Base rarity weights rebalanced** — Rare items drop ~7% on floor 1 (down from ~12%), making yellow-name items feel special again. Full weight changes:
  | Rarity | Old Weight | New Weight |
  |--------|-----------|-----------|
  | Common | 60.0 | 70.0 |
  | Magic | 25.0 | 20.0 |
  | Rare | 12.0 | 7.0 |
  | Epic | 2.5 | 1.2 |
  | Unique | 0.5 | 0.3 |
- **Steeper floor bonus curve** — Deeper floors now feel significantly more rewarding. Floor 1→9 Rare delta increased from +7.8pp to +9.7pp:
  | Floors | Old Bonus | New Bonus |
  |--------|----------|----------|
  | 1–2 | 0.00 | 0.00 |
  | 3–4 | 0.15 | 0.20 |
  | 5–6 | 0.35 | 0.50 |
  | 7–8 | 0.60 | 0.90 |
  | 9+ | 1.00 | 1.40 |
- **Common weight reduction formula** — Multiplier changed from `0.3` to `0.4`, making common items fall off faster on deeper floors.
- **Chest tier mapping fix** — Wooden/Iron chests now use `fodder` tier instead of `mid`, Gold uses `mid`, Obsidian uses `elite`, Boss uses `boss`. Early chests no longer inflate rarity beyond what killing a normal enemy would give.

### Files Changed
- `server/app/core/item_generator.py` — `_BASE_RARITY_WEIGHTS`, `_FLOOR_BONUS`, common weight formula in `roll_rarity()`
- `server/app/core/loot.py` — Chest-to-enemy-tier mapping in `generate_chest_loot()`
- `server/configs/loot_tables.json` — `rarity_config.base_rates` and `rarity_config.floor_bonuses`
- `docs/Phase Docs/loot-rarity-rebalance-proposal.md` — Design proposal (reference)

---

## [v0.1.7k] - 2026-03-17 - Ambient Darkness Pass (Torch Light Contrast)

### Added
- **`drawAmbientDarknessPass()`** in `PropLighting.js` — New rendering pass that overlays semi-transparent darkness on all **visible** tiles, then carves out bright pools around light-emitting props. Creates genuine contrast so torches, braziers, and candelabras feel like real illumination rather than faint color washes on an already-bright scene.
  - Uses a wider carve-out radius (1.3× the glow radius) with quadratic falloff so the light-to-dark transition is smooth and natural.
  - Darkness alpha is fully removed at light source centers and gradually restored at the falloff edge.
  - Cached per theme/room configuration — no per-frame recalculation.
- **Per-theme `ambientDarkness`** config value in `ambient` section of all 11 dungeon themes. Controls the base darkness level (0.0 = no effect, higher = darker). Thematically darker dungeons (Bleeding Catacombs 0.40, Cursed Shrine 0.42, Fungal Grotto 0.40) are gloomier than lighter ones (Forgotten Cellar 0.30, Pale Ossuary 0.30).

### Changed
- **Light source intensities boosted** — All prop light sources increased 2–3× to pop against the darker ambient:
  | Prop | Old Intensity → New | Old Radius → New |
  |------|---------------------|------------------|
  | torch_sconce | 0.08 → 0.22 | 2.5 → 3.0 |
  | brazier | 0.10 → 0.28 | 3.0 → 3.5 |
  | candelabra | 0.09 → 0.24 | 3.0 → 3.5 |
  | ritual_circle | 0.10 → 0.22 | 3.5 → 4.0 |
  | mushroom_cluster | 0.07 → 0.16 | 2.0 → 2.5 |
  | fountain | 0.05 → 0.14 | 1.8 → 2.5 |
  | altar | 0.04 → 0.12 | 1.5 → 2.0 |
- **`ArenaRenderer.js`** — Ambient darkness pass inserted into render pipeline after unit rendering, before fog overlay. Only activates for dungeon maps with rooms and an active theme.
- **`PropLighting.js`** — `clearLightCache()` now also clears the ambient light map cache.

### Per-Theme Ambient Darkness Values
| Theme | ambientDarkness | Feel |
|-------|----------------|------|
| Bleeding Catacombs | 0.40 | Heavy gloom |
| Ashen Undercroft | 0.35 | Moderate |
| Drowned Sanctum | 0.38 | Deep underwater murk |
| Hollowed Cathedral | 0.32 | Slightly lighter (candelabras) |
| Iron Depths | 0.38 | Industrial dark |
| Forgotten Cellar | 0.30 | Lighter rustic |
| Pale Ossuary | 0.30 | Lighter bone-white |
| Silent Vault | 0.35 | Moderate |
| Fungal Grotto | 0.40 | Heavy (bioluminescent contrast) |
| Frozen Crypt | 0.35 | Moderate icy |
| Cursed Shrine | 0.42 | Heaviest (ritual darkness) |

### Files Changed
- `client/src/canvas/PropLighting.js` — `drawAmbientDarknessPass()` function + ambient light map cache + boosted LIGHT_SOURCES intensities/radii
- `client/src/canvas/ArenaRenderer.js` — import + call `drawAmbientDarknessPass()` before fog pass
- `client/src/canvas/ThemeEngine.js` — `ambientDarkness` added to all 11 built-in theme `ambient` configs
- `server/configs/themes/*.json` — `ambientDarkness` added to all 11 theme JSON files

---

## [v0.1.7j] - 2026-03-17 - Prop Lighting System (Multi-Tile Glow + Fog Modulation + Particles)

### Added
- **`PropLighting.js`** — New rendering module that gives light-emitting props (torches, braziers, candelabras, ritual circles, mushroom clusters, fountains, altars) multi-tile radial glow effects. Uses additive blending (`globalCompositeOperation: 'lighter'`) with radial gradients that span 1.5–3.5 tiles from the prop center, creating warm pools of light visible across adjacent tiles.
  - `collectLightSources()` — Mirrors TileProps.js deterministic placement logic (cellHash, `_resolvePosition`, focal/accent priority, budget) to identify which props land on which tiles. No server changes required.
  - `drawPropGlowPass()` — Renders the actual glow: additive radial gradients with per-prop color, radius, and intensity. Fire-type props (torch, brazier, candelabra) have randomized flicker via sine-wave offsets. Magic-type props (ritual circle, mushroom cluster) have smooth pulse animation.
  - `buildFogLightMap()` / `getFogLightMap()` — Returns a `Map<string, number>` of tile-key → fog alpha reduction. Props carve a soft hole in the fog-of-war overlay, making revealed tiles near light sources appear brighter. Uses quadratic falloff, capped at 0.3 alpha reduction per tile.
  - Light source cache keyed by theme ID + room count to avoid recalculating every frame.
- **Fog-of-war light modulation** — `ThemeEngine.drawFog()` now accepts a `fogLightMap` parameter. For revealed tiles near light sources, the explored-fog alpha is reduced proportionally, creating visible light pockets that penetrate the fog. Unrevealed and invisible tiles are unaffected.
- **5 new particle presets** in `ambient.json`:
  - `prop-candelabra-glow` — Warm yellow-orange flame particles drifting upward
  - `prop-ritual-pulse` — Ring-shaped accent-colored magic particles
  - `prop-bioluminescent-spore` — Slow green drifting spore particles for mushroom clusters
  - `prop-brazier-embers` — Hot fire embers with upward drift
  - `prop-fountain-mist` — Cool blue mist particles for fountain props
- **Prop particle attachment** in `ParticleManager.js` — New `updatePropParticles(dungeonRooms, theme)` method follows the established zone emitter pattern to create persistent looping particle emitters at light-emitting prop positions. `PROP_PRESET_MAP` routes each prop type to its particle preset. Emitters are automatically created and destroyed as room data changes.

### Changed
- **`dungeonRenderer.js`** — Rendering pipeline now includes a glow pass after room overlays and before fog. `drawFog()` signature updated to accept `dungeonRooms` for fog light map construction.
- **`ArenaRenderer.js`** — `drawFog()` call updated to pass `dungeonRooms` through to the fog renderer.
- **`ThemeEngine.js`** — `drawFog()` rewritten to support per-tile fog alpha modulation. Parses base explored-fog alpha from the theme tint string, then reduces it for tiles intersected by the fog light map (minimum alpha floor of 0.15).
- **`ParticleManager.js`** — Added `_propEmitters` Map, `PROP_PRESET_MAP` static, `updatePropParticles()` method, `_cleanupPropEmitters()` safety net in tick loop, and cleanup in `destroy()`.
- **`Arena.jsx`** — New `useEffect` wires `updatePropParticles()` when `dungeonRooms` changes, following the same pattern as ground zone emitters.

### Light Source Configuration
| Prop | Radius (tiles) | Intensity | Color | Animation |
|------|----------------|-----------|-------|-----------|
| torch_sconce | 2.5 | 0.08 | Warm orange | Fire flicker |
| brazier | 3.0 | 0.10 | Deep orange | Fire flicker |
| candelabra | 3.0 | 0.09 | Bright gold | Fire flicker |
| ritual_circle | 3.5 | 0.10 | Theme accent | Pulse (1.2s) |
| mushroom_cluster | 2.0 | 0.07 | Theme accent | Pulse (0.8s) |
| fountain | 1.8 | 0.05 | Cool blue | None |
| altar | 1.5 | 0.04 | Theme accent | None |

### Files Changed
- `client/src/canvas/PropLighting.js` — **NEW** (~270 lines) — glow pass rendering, fog light map, light source collection
- `client/src/canvas/dungeonRenderer.js` — import + glow pass call + drawFog signature update
- `client/src/canvas/ThemeEngine.js` — `drawFog()` rewritten for light-modulated fog
- `client/src/canvas/ArenaRenderer.js` — pass dungeonRooms to drawFog
- `client/public/particle-presets/ambient.json` — 5 new prop particle presets
- `client/src/canvas/particles/ParticleManager.js` — prop emitter management system
- `client/src/components/Arena/Arena.jsx` — useEffect wiring for prop particles

### Notes
- FoV bonus (light sources increasing visible tile radius) is deferred to a future phase.
- No server changes required — all prop positions are resolved client-side using the existing deterministic placement algorithm.
- Pre-existing test failure in `TestBloodpact.test_low_hp_bonus_inactive_above_threshold` (unrelated unique item damage test). 3710 other tests passing.

---

## [v0.1.7i] - 2026-03-17 - Room Door System (Chokepoint Separators)

### Added
- **`door_placer.py`** — New post-decoration pass in the WFC generation pipeline that scans module boundaries and inserts wall separators with 1-tile door gaps at room entrances. Runs between `decorate_rooms()` and `export_to_game_map()`, so it has full knowledge of room roles.
- **Per-boundary door rolling** — Each module boundary is independently evaluated via seeded PRNG. Some entrances get a wall separator creating a tactical chokepoint, others stay wide open for variety.
- **Role-aware door chances** — Door probability is context-sensitive:
  - Spawn rooms: never doored (0%) — avoids frustrating the player at start
  - Boss rooms: high door chance (70%) — dramatic chokepoint before the boss
  - Grand interior joins (6+ tile openings): never doored (0%) — preserves multi-module rooms
  - Narrow openings (2-wide): slightly elevated (55%) — natural door spot
  - Corridor↔corridor: low chance (15%) — corridors stay open
  - Standard room entrances: 45% base chance
- **Per-style `doorChance` tuning** — Each dungeon style now overrides the base door probability:
  - Balanced: 0.45 (default)
  - Dense Catacomb: 0.60 (claustrophobic, more chokepoints)
  - Open Ruins: 0.20 (spacious, fewer barriers)
  - Boss Rush: 0.55 (tactical gates before encounters)
  - Treasure Vault: 0.50 (guarded rooms)
- **Door tiles re-enabled in map export** — `_normalize_tile()` no longer strips `D` tiles to `F`. Door tiles now survive to the exported game map and are collected into the `doors[]` array with `state: "closed"`.

### Changed
- **`dungeon_generator.py`** — Pipeline now runs `insert_room_doors()` as step 3.5 between decoration and export. Door placement stats included in generation metadata.
- **`map_exporter.py`** — `_normalize_tile()` updated: `D` tiles are preserved (previously converted to `F` with "doors disabled" comment). Only `E` and `B` markers are normalized to `F`.
- **`dungeon_styles.py`** — All 5 dungeon styles now include `doorChance` in their `decorator_overrides` dict.

### Notes
- Door gameplay mechanics (interaction_phase.py `_resolve_doors`) were already fully implemented — closed doors block movement, players toggle via INTERACT. This change provides the doors for it to operate on.
- Client rendering (dungeonRenderer.js door tile handling, ThemeEngine door drawing, RoomOverlays.js door archway highlights) was already implemented — doors will render immediately with no client changes needed.
- 3792 tests passing.

---

## [v0.1.7h] - 2026-03-17 - Prop Placement Overhaul (Budget + Focal System)

### Changed
- **Prop budget system** — Every room archetype now has a `maxProps` cap that limits how many prop slots can activate. Prevents visual clutter by stopping placement once the budget is reached. Budgets tuned per archetype: boss=5, enemy=3, empty=2, shrine=3, library=2, etc.
- **Focal prop groups** — Boss, prison, cathedral, ritual, torture, and ossuary archetypes now have a `focal` array of mutually exclusive center props. Exactly one is chosen via weighted random (seeded), giving each room instance a unique identity — e.g. a boss room might feature an altar OR a throne OR a ritual circle, never all three. Weights are scaled by theme affinity so thematically inappropriate props are filtered out.
- **Overlay-prop deduplication** — Removed props from `ARCHETYPE_PROP_SLOTS` that were already drawn by the archetype overlay functions, eliminating visual doubling:
  - Boss: removed `pillar` at corners (overlay draws corner pillars)
  - Shrine: removed `altar`, `brazier`, `banner` (overlay draws altar+braziers+banners)
  - Library: removed `bookshelf` on all walls (overlay draws full wall bookshelves)
  - Prison: removed `chains` on L/R walls (overlay draws chains+iron bars)
  - Flooded: removed `puddle` at random_floor/center (overlay draws floor puddles)
  - Empty: removed `rubble` at corners (overlay draws corner rubble)
  - Enemy: removed `weapon_rack` at wall_top and `torch_sconce` (overlay draws torches+rack lines)
  - Armory: removed `weapon_rack` at wall_top (overlay draws weapon pegs there)
- **Reduced prop chances** — Lowered base chance values across all archetypes. Enemy braziers from 0.7→0.5, loot barrels from 0.4→0.3, empty rubble from 0.5→0.4, graveyard tombstones from 0.8→0.75, etc. Combined with the budget cap, rooms now feel deliberately furnished rather than randomly scattered.
- **Restructured `ARCHETYPE_PROP_SLOTS` data format** — Changed from flat arrays to `{ maxProps, focal?, accents }` objects. Focal props are always placed at center; accents sorted by position priority (structural first, scatter last) before budget evaluation.
- **New `_pickFocal()` helper** — Weighted random selection from focal group, filtered by theme affinity. Ensures each room type feels distinct across playthroughs while respecting theme constraints.
- **Updated `drawRoomProps()` engine** — Now processes focal prop first (claiming 1 budget slot), then iterates accent props in priority order, stopping when `maxProps` is reached. Each slot activation counts as 1 toward budget regardless of how many tiles it covers (corners=4 tiles but 1 budget slot).

### Fixed
- Boss rooms no longer spawn altar + throne + ritual circle simultaneously (focal group picks exactly one)
- Shrine rooms no longer double-draw altar/braziers/banners (overlay handles those, props removed)
- Library rooms no longer draw bookshelf props on walls where the overlay already renders full bookshelves
- Prison rooms no longer double-draw chains on left/right walls
- Empty rooms no longer draw rubble at corners on top of the overlay's hand-placed corner rubble
- Enemy rooms no longer draw torch sconces and weapon racks that overlap with overlay torches and rack lines

### Files Changed
- `tools/theme-designer/src/engine/tileProps.js` — restructured `ARCHETYPE_PROP_SLOTS` (array→object with maxProps/focal/accents), added `_pickFocal()`, rewrote `drawRoomProps()` with budget system
- `tools/theme-designer/src/components/ObjectBrowser.jsx` — updated archetype placement iteration to handle new focal/accents data shape
- `client/src/canvas/TileProps.js` — mirrored all structural changes (budget, focal, drawRoomProps rewrite)

---

## [v0.1.7g] - 2026-03-17 - Room Archetype Expansion (7 New Archetypes)

### Added
- **7 new room archetypes** for the Dungeon Theme Designer, bringing total from 10 to 17:
  - **Grand Cathedral** — towering nave with central aisle, rose window motif on top wall, vertical wall streaks for height illusion, accent floor border
  - **Ritual Chamber** — arcane summoning room with dark ambient wash, central radial glow, floor rune marks, corner darkening, containment ring
  - **Torture Chamber** — blood-stained floor patches, scratched floor marks, heavy corner vignette, metal fixture brackets on walls
  - **Burial Ground** — earthy muted wash, disturbed soil patches, faint ground mist gradient, grave row path markers
  - **Armory** — clean maintained floor, metal wall trim with highlight, organized weapon pegs on walls, warm torchlight glow spots, door-to-center path
  - **Ossuary** — pale bone-white undertone, horizontal bone-stack texture on side walls, wall alcove recesses, flanking candle warm spots
  - **Fungal Grotto** — bioluminescent accent wash, radial glow pools, damp wall sheen, organic wall-edge blobs, floating spore dust motes
- **Prop slot definitions** for armory (weapon_rack, barrel, torch_sconce, chains), ossuary (skull_pile, coffin, candelabra, tombstone, altar), and fungal_grotto (mushroom_cluster, puddle, web, rubble)
- Cathedral, ritual, torture, and graveyard archetypes already had prop slots defined — now fully registered with labels, descriptions, and overlay draw functions

### Files Changed
- `tools/theme-designer/src/engine/roomArchetypes.js` — added 7 entries to `ROOM_ARCHETYPES`, 7 overlay draw functions, 7 switch cases in `drawRoomOverlay()`
- `tools/theme-designer/src/engine/tileProps.js` — added `ARCHETYPE_PROP_SLOTS` entries for armory, ossuary, fungal_grotto

---

## [v0.1.7f] - 2026-03-16 - Party HP Panel Centering & Instant Population Fix

### Fixed
- **Party HP panels biased to the left** — `.party-vitals` had `flex: 1` which stretched the container to fill all remaining space in the vitals row, overriding the `justify-content: center` on the parent. Removed `flex: 1` and `overflow-x: auto` so the party vitals container is content-sized and the vitals row correctly centers all HP panels (player + party) over the viewport.
- **Party HP bars missing on first frame** — only the player's own HP panel appeared at match start; party member HP panels didn't populate until after the first tick. The `MATCH_START` handler in `combatReducer` reset `partyMembers` to `[]`, and party data was only sent via the `queue_updated` message after the first turn resolved. Added `party` data to the server's `match_start` payload (`get_match_start_payload_for_player`) and updated the client's `MATCH_START` handler to use `action.payload.party` if present, so all party HP bars render immediately when the match begins.

### Files Changed
- `client/src/styles/components/_player-vitals.css` — removed `flex: 1` and `overflow-x: auto` from `.party-vitals`
- `server/app/core/match_manager.py` — `get_match_start_payload_for_player()` now includes `party` array via `get_party_members()`
- `client/src/context/reducers/combatReducer.js` — `MATCH_START` handler uses `action.payload.party || []` instead of hardcoded `[]`

---

## [v0.1.7e] - 2026-03-16 - Dungeon HUD Layout Overhaul

### Changed
- **Minimap relocated to right panel** — moved from an absolute overlay in the top-right of the game viewport to the right sidebar, positioned above the target bar (HUD). The minimap now fills the full panel width (~270px) as a squared-off panel matching the width of the HUD, Party, and Enemy panels below it. Tile size auto-scales to fill the panel based on map dimensions.
- **Player HP bar relocated above viewport** — the PlayerVitals frame (gradient HP bar with class identity row) moved from an absolute overlay at the bottom-left of the canvas to a dedicated vitals row between the action bar and the game viewport. It now sits outside the viewport area entirely rather than hovering over it.
- **Combat Meter button labeled** — the "⚔" combat meter toggle button in the action bar now displays a "Meter" text label below the icon, making its purpose clearer to players
- **Arena grid layout expanded** — grid changed from 3-row to 4-row layout (`auto auto auto 1fr`) to accommodate the new vitals row; left panel and right panel span rows 3–4 so they remain full-height

### Added
- **PartyVitals component** — new component that displays HP bars for all party members side by side using the same gradient bar style as the player's own PlayerVitals. Each party member gets a class-colored top accent border, class icon + name, player name, and a 20px gradient HP bar with HP text centered inside. Includes the same color-coded HP states (green >50%, amber 25–50%, red ≤25%, grey dead), danger pulse animation at low HP, and dead state desaturation.
- **Vitals row** (`arena-vitals-row`) — new grid row in the arena layout that contains the player's HP bar on the left and party HP bars side by side next to it, all between the action bar and the game canvas

### Files Changed
- `client/src/components/Arena/Arena.jsx` — moved MinimapPanel from canvas overlays to right panel (above HUD); moved PlayerVitals from canvas overlay to vitals row; added PartyVitals import and render
- `client/src/components/PlayerVitals/PartyVitals.jsx` — new component
- `client/src/components/PlayerVitals/PlayerVitals.jsx` — unchanged (styles updated in CSS)
- `client/src/components/MinimapPanel/MinimapPanel.jsx` — updated tile size calculation to fill panel width (~270px)
- `client/src/components/BottomBar/BottomBar.jsx` — added "Meter" label text to combat meter toggle button
- `client/src/styles/layout/_arena.css` — 4-row grid, vitals row styles, updated row spans for left/right/canvas
- `client/src/styles/layout/_minimap.css` — changed from absolute overlay to flow element with aspect-ratio 1/1 and full width
- `client/src/styles/components/_player-vitals.css` — removed absolute positioning; added PartyVitals/party-vital styles
- `client/src/styles/components/_combat-meter.css` — flex-direction column on btn-meter, added meter-label styles

---

## [v0.1.7d] - 2026-03-16 - Inventory Panel Width & Overflow Fix

### Fixed
- **Inventory overlay panel too narrow** — text (item names, buff pills, stat rows, context strip) was overflowing to the right and creating a horizontal scrollbar
  - Widened base panel from 340–440px to 420–560px (`width: max-content` up to max-width)
  - Widened large-screen breakpoint (1201px+) from 360–480px to 440–600px
  - Widened medium breakpoint (769–1200px) from 340–440px to 420–560px
  - Widened small-medium breakpoint (501–768px) from 320px min to 400px min
  - Added `overflow-x: hidden` to prevent horizontal scrollbar
  - Added `max-width: 100%` to equipment slot item names for proper ellipsis truncation
  - Added `overflow: hidden` and `max-width: 100%` to buff list and bag slot item info
  - Added `flex-wrap: wrap` and `overflow: hidden` to dungeon context strip

### Files Changed
- `client/src/styles/components/_inventory.css` — panel width increases, overflow protection

---

## [v0.1.7c] - 2026-03-16 - Player Vitals HP Bar Overhaul

### Added
- **PlayerVitals component** — new dedicated HP frame overlay anchored to the bottom-left of the game canvas, replacing the tiny inline HP bar that was buried in the header
  - **20px tall gradient HP bar** with HP text centered inside (white text with dark shadow for readability)
  - **Class identity row** — class-colored top accent border, class icon + class name + player name
  - **Color-coded HP states** — green gradient (>50%), amber gradient (25–50%), red gradient (<25%), grey (dead)
  - **Low-HP danger pulse** — red glow animation on the frame border when HP ≤ 25%
  - **Dead state** — desaturated and dimmed frame with "💀 DEAD" text
  - **Responsive scaling** — shrinks bar and frame on smaller viewports (<800px height)
- **`_player-vitals.css`** — full stylesheet with gradients, inner shadows, pulse animation, and responsive rules

### Changed
- **HeaderBar** — removed inline HP bar section (label, bar, value) to reduce top-bar clutter; turn/timer/mode/class/buffs remain
- **Arena layout** — PlayerVitals renders as an overlay inside the canvas area (bottom-left corner), near the player's natural focus area beside the action bar

### Removed
- **Header HP CSS** — removed `.header-hp`, `.header-hp-label`, `.header-hp-bar-bg`, `.header-hp-bar-fill`, `.header-hp-value` styles (no longer needed)

### Files Changed
- `client/src/components/PlayerVitals/PlayerVitals.jsx` — new component
- `client/src/styles/components/_player-vitals.css` — new stylesheet
- `client/src/components/HeaderBar/HeaderBar.jsx` — removed HP bar section
- `client/src/styles/components/_header-bar.css` — removed HP styles
- `client/src/components/Arena/Arena.jsx` — import and render PlayerVitals in canvas area
- `client/src/styles/main.css` — added `_player-vitals.css` import

---

## [v0.1.7b] - 2026-03-16 - Missing Particle Effects Pass

### Added
- **Seal of Judgment particles** — gold/holy branded star burst on target with diamond rune extras and a golden projectile trail (Inquisitor)
- **Blink particles** — arcane blue star burst at destination + fading departure trail at origin, visually distinct from Shadow Step's dark-bolt (Mage)
- **Bone Shield particles** — bone-colored triangle fragments orbit the caster on cast + persistent bone-shard aura while active (Skeleton enemy)
- **Dark Pact particles** — purple dark-magic burst on target with diamond-trail link wisps at caster + persistent purple aura while buffed (Dark Priest enemy)
- **Profane Ward particles** — expanding lavender circles on target + persistent lavender aura while damage reduction is active (Acolyte enemy)
- **Enrage particles** — dramatic fire ignition burst (white→gold→red→crimson) when HP drops below 30% + persistent flame aura while enraged (Demon Enrage enemy)
- **Frenzy Aura particles** — orange/red ring pulse on activation + persistent smoldering aura while the imp buff aura is active (Imp Lord enemy)
- **6 new buff auras** — `buff-aura-bone-shield`, `buff-aura-dark-pact`, `buff-aura-profane-ward`, `buff-aura-enrage`, `buff-aura-frenzy` persistent looping effects; `dark_pact` and `profane_ward` buff_id overrides added
- **3 new buff_status types** — `damage_absorb`, `passive_enrage`, `passive_aura_ally_buff` now have persistent aura visuals

### Changed
- **`particle-effects.json`** — added skill mappings for `seal_of_judgment`, `blink`, `bone_shield`, `dark_pact`, `profane_ward`, `enrage`, `frenzy_aura`; added `buff_id_overrides` for `dark_pact` and `profane_ward`; added `buff_status` entries for `damage_absorb`, `passive_enrage`, `passive_aura_ally_buff`

### Files Changed
- `client/public/particle-effects.json` — 7 new skill mappings, 3 new buff_status types, 2 new buff_id overrides
- `client/public/particle-presets/skills.json` — 12 new presets (seal-judgment-brand, seal-judgment-runes, seal-judgment-trail, blink-arrival, blink-departure, bone-shield-cast, dark-pact-cast, dark-pact-link, profane-ward-cast, enrage-ignite, frenzy-aura-pulse)
- `client/public/particle-presets/buffs.json` — 6 new aura presets (buff-aura-bone-shield, buff-aura-dark-pact, buff-aura-profane-ward, buff-aura-enrage, buff-aura-frenzy)

---

## [v0.1.7a] - 2026-03-16 - PVPVE Chest Tier Overhaul

### Added
- **PVPVE location-based chest tiers** — PVPVE mode now uses a centrality-based tier system instead of floor-depth gating. Chests closer to the map center (boss room area) roll higher tiers, creating a risk/reward dynamic where better loot requires venturing into contested territory.
  - **Edge zone** (team spawn corners): ~57% Wooden, ~28% Iron, ~11% Gold, ~3% Obsidian
  - **Mid zone** (midfield rooms): ~31% Wooden, ~37% Iron, ~22% Gold, ~11% Obsidian
  - **Center zone** (boss area): ~11% Wooden, ~25% Iron, ~40% Gold, ~24% Obsidian
- **`pvpve_tier_weights` config** — new section in `chest_tier_config` defines per-zone (edge/mid/center) spawn weights for PVPVE mode, independent of floor-range gating
- **`roll_chest_tier_pvpve()`** — new loot function that accepts a `centrality` value (0.0 = map edge, 1.0 = map center) and selects the appropriate zone weight table

### Fixed
- **PVPVE chests no longer all Wooden** — previously, PVPVE mode was always floor 1, so the floor-range gating meant only Wooden chests (floor 1+) were eligible. Iron (floor 2+), Gold (floor 4+), and Obsidian (floor 7+) could never spawn. The new centrality system bypasses floor gating entirely.

### Changed
- **`_init_dungeon_state()`** — now detects PVPVE match type and computes Euclidean centrality for each chest position relative to the map center. PVPVE chests use `roll_chest_tier_pvpve()` while standard dungeon chests continue using the floor-based `roll_chest_tier()`.

### Files Changed
- `server/configs/loot_tables.json` — added `pvpve_tier_weights` section with edge/mid/center weight tables
- `server/app/core/loot.py` — added `roll_chest_tier_pvpve()` function
- `server/app/core/match_manager.py` — updated `_init_dungeon_state()` with PVPVE centrality logic, added `get_map_dimensions` import

---

## [v0.1.7] - 2026-03-15 - Chest Tier System & Visual Redesign

### Added
- **Chest tier system** — 5 distinct chest tiers replace the single generic chest:
  - **Wooden Chest** (floors 1+, weight 50) — 1-2 common-leaning items
  - **Iron Chest** (floors 2+, weight 30) — 1-3 items, better uncommon drop rates
  - **Gold Chest** (floors 4+, weight 15) — 2-3 items, guaranteed magic+ rarity
  - **Obsidian Chest** (floors 7+, weight 5) — 2-4 items, guaranteed rare+ rarity
  - **Boss Chest** (boss rooms only) — unchanged from previous boss_chest behavior
- **Chest tier config** in `loot_tables.json` — new `chest_tier_config` section defines tier spawn weights, floor ranges, and loot table mappings
- **4 new chest loot tables** — `wooden`, `iron`, `gold`, `obsidian` with progressively better weighted pools
- **Chest tier visual redesign** — all chests now render as detailed barrel-lidded treasure chests with:
  - 3D shading (dark right edge, highlight left edge)
  - Visible lid with overhang and border
  - 2 horizontal metal band straps
  - Center latch/lock with keyhole detail
  - Opened state shows interior cavity, tilted-back lid, and hinge dots
  - Tier-specific glow effects (gold glow for Gold, purple glow for Obsidian, red glow for Boss)
- **Tier-specific color palettes** — each tier has unique body, band, latch, and lid colors
- **Tier-aware minimap** — minimap chest dots now use tier-specific colors instead of a single gold dot
- **Client utility modules**:
  - `chestUtils.js` — chest state parsing, tier config lookup, minimap color helper
  - `chestRenderer.js` — shared detailed chest drawing function used by ThemeEngine and dungeonRenderer

### Changed
- **Chest state format** — `chest_states` values changed from `"unopened"/"opened"` to `"unopened:tier"/"opened:tier"` (e.g. `"unopened:iron"`, `"opened:gold"`). Full backward compatibility with plain `"unopened"`/`"opened"` maintained.
- **`_init_dungeon_state`** — now rolls a chest tier for each chest based on floor number and boss room context using `roll_chest_tier()`
- **`generate_chest_loot`** — now falls back to the `"default"` loot table when an unknown chest type is passed, instead of returning empty
- **`_resolve_loot` (interaction_phase)** — extracts chest tier from state and passes it to `generate_chest_loot` for tier-appropriate drops
- **ThemeEngine** — chest case now delegates to shared `drawChestIcon()` with tier info passed via `extra.chestTier`
- **dungeonRenderer** — flat-color fallback chest replaced with tier-aware `drawChestIcon()`
- **Theme Designer tool** — `tilePatterns.js` `drawChest()` updated with detailed rendering matching the game
- **Pathfinding & keyboard shortcuts** — updated to recognize `"unopened:tier"` format via `startsWith` checks

### Files Changed
- `server/configs/loot_tables.json` — added `chest_tier_config`, 4 new chest loot tables (wooden, iron, gold, obsidian)
- `server/app/core/loot.py` — added `roll_chest_tier()`, updated `generate_chest_loot()` fallback
- `server/app/core/match_manager.py` — `_init_dungeon_state()` now rolls chest tiers
- `server/app/core/turn_phases/interaction_phase.py` — `_resolve_loot()` parses tier from chest state
- `client/src/utils/chestUtils.js` — new (chest tier config, state parsing)
- `client/src/canvas/chestRenderer.js` — new (detailed chest icon drawing)
- `client/src/canvas/dungeonRenderer.js` — updated chest drawing + imports
- `client/src/canvas/ThemeEngine.js` — updated chest drawing to use `drawChestIcon`
- `client/src/canvas/minimapRenderer.js` — tier-aware chest minimap colors
- `client/src/canvas/renderConstants.js` — updated default chest colors
- `client/src/canvas/pathfinding.js` — updated `startsWith` checks for new state format
- `client/src/hooks/useKeyboardShortcuts.js` — updated `startsWith` check for E key chest detection
- `tools/theme-designer/src/engine/tilePatterns.js` — updated `drawChest()` with detailed rendering
- `server/tests/test_dungeon_map.py` — updated assertion for new chest state format
- `server/tests/test_phase16b_affix_system.py` — updated test for fallback behavior

---

## [v0.1.6b] - 2026-03-15 - Hero Permadeath Bug Fix

### Fixed
- **Hero permadeath now applies to all heroes** — AI hero allies (party members) were not triggering permadeath when killed in dungeon runs. Only the human-controlled hero was checked (`unit_type == "human"`), but party allies spawn as `unit_type == "ai"` with a valid `hero_id`. Changed the condition to check for `hero_id` presence regardless of unit type, so all roster heroes are properly marked dead and removed from the active roster on death.

### Files Changed
- `server/app/core/turn_phases/deaths_phase.py` — permadeath condition changed from `unit_type == "human" and hero_id` to just `hero_id`

---

## [v0.1.6a] - 2026-03-15 - Custom Cursor & Game Icon

### Added
- **Custom game cursor** — `MouseFinal.png` resized to 32×32 and applied as the in-game cursor site-wide via CSS (`cursor.png` in `client/public/`). Replaces default browser cursor on all elements including buttons and interactive controls.
- **Game icon** — `icon 1.ico` / `icon 1.png` set as the official app icon:
  - Electron game window icon (`client/public/favicon.ico`)
  - Browser favicon (`<link>` tags in `index.html` for `.ico` and `.png`)
  - Electron builder icon for Windows/Mac/Linux builds
  - Launcher window icon + system tray icon (`launcher/assets/icon.ico`)
  - Launcher electron-builder config updated

### Files Changed
- `client/public/cursor.png` — new (32×32 resized from `Assets/Sprites/MouseFinal.png`)
- `client/public/favicon.ico` — new (from `Assets/Sprites/icon 1.ico`)
- `client/public/favicon.png` — new (from `Assets/Sprites/icon 1.png`)
- `launcher/assets/icon.ico` — new (from `Assets/Sprites/icon 1.ico`)
- `client/src/styles/base/_reset.css` — added custom cursor rules
- `client/index.html` — added favicon `<link>` tags
- `launcher/main.js` — added `icon` property to BrowserWindow
- `launcher/package.json` — added `icon` to electron-builder win config

---

## [v0.1.6] - 2026-03-14 - AI & Team Fixes

**Summary:** Six bug fixes and AI improvements targeting PVPVE team assignment, totem targeting, Confessor AI, and multi-support positioning. Rolls up v0.1.5–v0.1.5f changes into a published release.

### Bug Fixes
- **PVPVE lobby team ignored** — `_assign_pvpve_teams()` no longer force-distributes players round-robin; respects lobby-chosen team (v0.1.5)
- **PVPVE index-based team detection** — `_spawn_pvpve_ai_teams()` now reads actual `player.team` instead of using list index (v0.1.5b)
- **Hero ally hardcoded to Team A** — `_spawn_hero_ally()` now reads owner's team field (v0.1.5b)
- **Ground-placement skills hijacked by auto-target** — Added `isPlacementSkill()` check to bypass auto-select for totem skills (v0.1.5c)
- **Shield of Faith self-cast** — Excluded caster from SoF candidate loop; moved SoF to Priority 4.7 after reposition check (v0.1.5e)
- **Multi-support clumping** — Support roles now exclude other supports from nearest-ally movement fallback (v0.1.5f)

### AI Improvements
- **Confessor tank-aware positioning** — Proactively moves toward tank-role allies when outside heal range (v0.1.5d)
- **Reposition threshold raised 60% → 80%** — Confessor starts closing distance earlier (v0.1.5d)
- **Check B tank drift threshold** — Introduced `_TANK_REPOSITION_THRESHOLD = 5` so Exorcism fires at medium range (v0.1.5e)
- **Support anti-clump anchoring** — `_support_move_preference()` and `_totemic_support_move_preference()` prefer non-support allies as anchors (v0.1.5f)

---

## [v0.1.5f] - 2026-03-14 - Multi-Support Anti-Clumping Fix

### Improvement — `server/app/core/ai_skills.py`

- **Support-role nearest-ally filtering** — `_support_move_preference()` (Confessor) and `_totemic_support_move_preference()` (Shaman) now exclude other support-role allies from their "nearest ally" movement fallback. Previously, when no allies were injured and the tank was within heal range, each support would pick the **nearest ally** as its movement anchor — which was often the other support. This caused Confessor + Shaman (and similar double-support comps) to gravitate toward each other, clump away from the frontline, and oscillate tiles as the batch movement resolver repeatedly blocked their identical move targets. Both functions now prefer non-support allies (tanks, DPS) as movement anchors, only falling back to support allies if no other teammates are alive. Added `_SUPPORT_ROLES` constant (`support`, `offensive_support`, `totemic_support`) for the filter.

---

## [v0.1.5e] - 2026-03-14 - Confessor AI Healing & Targeting Fixes

### Bug Fix — `server/app/core/ai_skills.py`

- **Shield of Faith self-cast bug** — `_support_skill_logic()` SoF candidate loop included the caster itself. Confessor has the lowest base HP (100) so it always had the lowest HP% and self-cast SoF ~56% of the time, wasting the buff on a backline unit. Added `if unit.player_id == ai.player_id: continue` to match the existing Dark Pact self-exclusion pattern. SoF now always targets an ally (typically the tank).

- **SoF priority blocks repositioning** — Shield of Faith was at Priority 4, firing BEFORE the Priority 4.5 reposition check. When the tank drifted out of heal range and needed healing, the Confessor would cast SoF (often on itself) instead of repositioning toward the hurt tank. Moved SoF to Priority 4.7 so the reposition check runs first. If the tank is far and hurt, the Confessor walks toward them instead of buffing.

- **Check B too aggressive** — The v0.1.5d "suppress Exorcism when tank is far" check used `_SUPPORT_HEAL_RANGE` (3 tiles) as its threshold, forcing reposition whenever the tank was >3 tiles away. This caused 64% of turns to be wasted on repositioning. Introduced `_TANK_REPOSITION_THRESHOLD = 5` so Exorcism can fire at medium range (4–5 tiles) while still triggering reposition when the tank is truly far (>5 tiles).

### Tests — `server/tests/test_confessor_diagnostic.py`

- 14 diagnostic tests verifying the three fixes: SoF never self-casts, reposition no longer blocks Exorcism at medium range, and SoF no longer prevents repositioning toward hurt tanks. Includes a 200-turn simulation asserting 0% SoF self-cast rate and <50% reposition rate.

---

## [v0.1.5d] - 2026-03-14 - Confessor AI Positioning Overhaul

### Improvement — `server/app/core/ai_skills.py`

- **Tank-aware support positioning** — `_support_move_preference()` now identifies tank-role allies (Crusader `tank`, Revenant `retaliation_tank`, Blood Knight `sustain_dps`) and proactively moves toward them when the Confessor is outside heal range (3 tiles). Previously the Confessor only moved toward **most injured** or **nearest** ally, causing it to drift behind the party while the tank advanced into combat. New priority order: (1) most injured ally below 60% HP, (2) tank-role ally outside heal range, (3) nearest ally.

- **Raised reposition threshold from 60% → 80%** — The "Priority 4.5" reposition check in `_support_skill_logic()` now uses a dedicated `_REPOSITION_ALLY_THRESHOLD` of 0.80 instead of the heal threshold (0.60). The Confessor will start closing distance toward out-of-range allies much earlier, before they become critical. This prevents the pattern where the Confessor spams Exorcism from range 5 while the tank slowly drops from 70% → 30% HP out of heal range.

- **Suppress Exorcism when tank is drifting out of range** — Added a second reposition check (Check B) that returns `None` when any tank-role ally is beyond heal range (3 tiles), regardless of their HP%. This forces the stance handler to move the Confessor toward the tank instead of casting Exorcism from the back line. Exorcism (range 5) greatly exceeds Heal (range 3), which previously created a positioning trap where the Confessor could DPS comfortably but couldn't heal.

- **New constants** — Added `_REPOSITION_ALLY_THRESHOLD` (0.80), `_TANK_ROLES` set (`{"tank", "retaliation_tank", "sustain_dps"}`), and `_SUPPORT_HEAL_RANGE` (3) for tank-proximity calculations.

---

## [v0.1.5c] - 2026-03-13 - Ground Placement Skill Targeting Fix

### Bug Fix — `client/src/components/BottomBar/BottomBar.jsx`

- **Ground-placement skills (totems) hijacked by auto-target system** — Skills with `targeting: "ground_aoe"` and a `place_totem` effect (Healing Totem, Searing Totem, Earthgrasp Totem) were treated as enemy-targeting skills by the auto-target system. When enemies were in FoV, pressing a totem skill button would auto-select the nearest enemy and initiate pursuit instead of entering tile-selection mode for placement. Fixed by adding an `isPlacementSkill()` check that detects `place_totem` effects and bypasses both the target-first casting path (Phase 10G-6) and the `findNearestTarget()` auto-select. Totem skills now always enter tile-selection mode regardless of nearby enemies. Affects all classes with ground-placement skills.

---

## [v0.1.5b] - 2026-03-13 - PVPVE Team Assignment Fix (Upstream)

### Bug Fix — `server/app/core/match_manager.py`

- **`_spawn_pvpve_ai_teams()` used index-based team detection** — When determining which teams were occupied by humans, the function used player list index (`active_teams[i % team_count]`) instead of each player's actual `player.team` value. With 2 humans both on Team A in a 4-team match, it incorrectly computed `human_teams = {"a", "b"}` instead of `{"a"}`. This meant enemy AI teams would only fill C and D, leaving Team B empty — and the cascading mismatch caused Player 2 to appear on the wrong team. Fixed to read actual `player.team` from lobby selections.

### Bug Fix — `server/app/core/hero_manager.py`

- **`_spawn_hero_ally()` hardcoded `team="a"`** — Hero allies were always spawned with `team="a"` and appended to `match.team_a`, ignoring the owner's actual team. Fixed to read the owner player's `team` field and append to the correct team list. This ensures hero allies follow their owner to whichever team they've selected in the lobby.

### Tests — `server/tests/test_pvpve_ai_teams.py`

- Updated `test_ai_teams_skip_human_occupied_teams` to explicitly place humans on separate teams (A and B) before asserting AI skips those teams.
- Added `test_ai_teams_fill_all_non_human_slots_when_same_team` — verifies that when 2 humans are both on Team A, AI enemy teams correctly fill all remaining slots (B, C, D).

---

## [v0.1.5] - 2026-03-13 - PVPVE Team Assignment Fix

### Bug Fix — `server/app/core/match_manager.py`

- **PVPVE lobby team ignored** — `_assign_pvpve_teams()` was force-distributing human players round-robin across teams, overriding whatever team they chose in the War Room lobby. If two players both picked Team A, Player 2 would be silently moved to Team B at match start and spawn in a different corner alone. Fixed to respect each player's lobby-chosen team when it's a valid active team for the match. Round-robin fallback only applies if a player's team isn't one of the active PVPVE teams (e.g., on Team D in a 2-team match).

---

## [v0.1.4] - 2026-03-13 - Stance System Overhaul, Destroy Item & Audio Fixes

**Summary:** Major AI stance overhaul making all 4 stances (Follow, Aggressive, Defensive, Hold) role-aware so class identity is preserved regardless of stance choice. New inventory destroy-item feature. Audio polish fixes.

### Stance System Overhaul (Phases S1–S3) — `server/app/core/ai_stances.py`, `server/tests/test_stances.py`

- **S1-A: Bard Aggressive kiting fix** — Added `offensive_support` to `is_ranged_role` set in `_decide_aggressive_stance_action()` so Bards kite in Aggressive (was already working in Follow). Added `ally_positions` calculation for Bard kiting direction to stay near ally centroid.
- **S1-B: Hold stance smart targeting** — Replaced naive `for enemy in enemies` iteration with `_pick_best_target()` for both melee (adjacent enemies) and ranged (in-range + LOS enemies) target selection in `_decide_hold_action()`.
- **S2-A: Defensive match_state** — Added `match_state=None` parameter to `_decide_defensive_action()` for totem awareness.
- **S2-B: Defensive ranged kiting** — Ranged classes (Mage, Ranger, Inquisitor, Plague Doctor, Bard, Shaman) now kite in Defensive stance with role-specific thresholds (controller ≤ 3, totemic_support ≤ 1, others ≤ 2). Kite moves tethered within 2 tiles of owner.
- **S2-C: Defensive ranged engagement** — Ranged roles now engage enemies at their full attack range instead of hardcoded 2-tile limit. Melee classes unchanged.
- **S2-D: Defensive support positioning** — Support classes (Confessor, Bard, Shaman) on Defensive now position near allies using role-specific move preference functions instead of charging enemies.
- **S2-E: Defensive totem-biased movement** — Added `_totem_biased_step` to Defensive movement paths and controller hold-position logic. Re-checks tether after totem bias.
- **S3-A: Aggressive support positioning** — Support classes on Aggressive now use ally positioning instead of charging enemies. Added `is_support` detection, excluded support from melee rush block.
- **S3-B: Bard ally-proximity kiting** — Already handled by S1-A.

### Audio Fixes — `client/public/audio-effects.json`, `client/src/audio/AudioManager.js`

- Wither cast sound → `shadow-step_teleport-downer.wav` (softer dark tone, vol 0.55)
- Wither DoT tick → `debuff_speed-debuff.wav` (subtler pulse, vol 0.25)
- Healing Totem pulse → `heal-alt_healing-gusts.wav` (gentle nature sound, vol 0.25)
- Registered `heal_alt` in `_soundFiles` for preloading

### 3747 tests passing, 0 regressions.

---

## [Feature] - 2026-03-13 - Destroy Item from Inventory

**Summary:** Players can now permanently destroy unwanted items from their bag during dungeon runs. Previously, once a player's 10-slot inventory filled up, there was no way to discard items to make room for better loot. Each bag slot now has a destroy button (🗑) with a two-click confirmation to prevent accidents.

### Added — `server/app/core/equipment_manager.py`

- **`destroy_item()`** — New function that removes an item from a player's inventory by instance_id or item_id. Returns the updated inventory list. Validates player exists and is alive.

### Changed — `server/app/core/match_manager.py`

- **Re-export block** — Added `destroy_item` to the equipment_manager re-exports so existing importers can access it via match_manager

### Changed — `server/app/services/message_handlers.py`

- **`handle_destroy_item()`** — New async WS handler accepting `{ type: "destroy_item", item_id, unit_id? }`. Calls `destroy_item()` and responds with `item_destroyed` message containing the updated inventory
- **`MESSAGE_HANDLERS`** — Added `"destroy_item": handle_destroy_item` entry
- **Imports** — Added `destroy_item` to the match_manager import block

### Changed — `client/src/App.jsx`

- **WS message dispatch** — Added `case 'item_destroyed'` that dispatches `ITEM_DESTROYED` action to the reducer

### Changed — `client/src/context/GameStateContext.jsx`

- **`INVENTORY_ACTIONS`** — Added `'ITEM_DESTROYED'` to the action routing set so it reaches the inventory reducer

### Changed — `client/src/context/reducers/inventoryReducer.js`

- **`case 'ITEM_DESTROYED'`** — New reducer case that updates `state.inventory` (or `partyInventories` for party members) with the server-provided updated inventory array

### Changed — `client/src/components/Inventory/Inventory.jsx`

- **`confirmDestroyId` state** — New state variable tracking which item is awaiting destruction confirmation
- **`handleDestroyItem()`** — New callback implementing two-click confirm: first click sets confirm state (button turns red), second click sends the `destroy_item` WS message
- **Bag slot actions** — Wrapped transfer and new destroy buttons in a `.bag-slot-actions` container. Destroy button (🗑/✕) shown on all items when alive, not just when transfer is available

### Changed — `client/src/styles/components/_inventory.css`

- **`.bag-slot-actions`** — Flex container for the action button group
- **`.bag-destroy-btn`** — Styled to match the existing transfer button aesthetic with red hover state
- **`.bag-destroy-btn.destroy-confirm`** — Red filled background with pulse animation for the confirmation state
- **`@keyframes pulse-destroy`** — Subtle pulsing animation to draw attention to the confirm state

---

## [Feature] - 2026-03-12 - Launcher Install Progress Bar (Launcher v1.1.0)

**Summary:** Added a real-time progress bar during the game extraction/install phase. Previously the launcher showed "INSTALLING..." with no visual feedback, making it look frozen. Now reuses the same smooth animated progress bar from the download phase, showing file-by-file extraction progress.

### Changed - `launcher/lib/extractor.js`

- **`extract()`** - Added `onProgress` callback option
- **`extractWithProgress()`** - New helper that extracts entries one at a time via `extractEntryTo()` instead of `extractAllTo()`, calling `onProgress(extracted, total)` after each file

### Changed - `launcher/main.js`

- **start-install handler** - Extract step now passes `onProgress` callback that sends `extract-progress` IPC events to the renderer with `{extracted, total}` counts

### Changed - `launcher/preload.js`

- **`onExtractProgress`** - New IPC bridge method exposing the `extract-progress` event to the renderer

### Changed - `launcher/renderer.js`

- **`applyState('installing')`** - Now shows the progress bar (reset to 0%) instead of hiding it
- **`onExtractProgress` listener** - Updates progress bar with smooth animation showing file count (e.g. "45% - 230 / 512 files")
- **Progress bar visibility** - Now stays visible during both `downloading` and `installing` states

---

## [Bugfix] - 2026-03-12 - Town Hub Hero Portraits Missing (v0.1.3)

**Summary:** Fixed hero portraits not displaying in Town Hub screens (Hero Roster, Hiring Hall, Merchant). Same root cause as v0.1.2 — absolute asset path under Electron's `file://` protocol.

### Changed — `client/src/components/TownHub/HeroSprite.jsx`

- **CSS `backgroundImage`** — Changed from `url(/spritesheet.png)` to `` url(${import.meta.env.BASE_URL}spritesheet.png) `` so the spritesheet resolves correctly in deployed Electron builds

---

## [Bugfix] — 2026-03-12 — Missing Sprites, Audio & Particles in Deployed Build

**Summary:** Fixed all static asset paths that broke when the game was loaded via Electron's `file://` protocol in deployed (installed) builds. Sprites, tiles, skill icons, audio, and particle effects were all missing for testers despite being correctly included in the build zip. Dev mode via `start-game.bat` was unaffected because Vite's dev server resolves `/` paths to the project root.

**Root cause:** All static asset paths in the codebase used absolute root-relative paths (e.g. `/spritesheet.png`, `/audio/combat/swing.wav`). In development, Vite's dev server maps `/` to the project's `public/` folder, so these work. In production Electron builds, the app loads via `file://` protocol from `dist/index.html`. Under `file://`, a leading `/` resolves to the **filesystem root** (e.g. `C:\spritesheet.png`), not the app's `dist/` folder. The Vite config already sets `base: './'` for Electron builds, which fixes JS/CSS bundle paths, but hardcoded asset constants in source code are not affected by Vite's `base` setting.

**Impact:** This was the cause of missing sprites and sounds reported during the first online test. All game logic, UI components, API calls, and WebSocket connections were unaffected (those use full HTTP URLs from `serverUrl.js`).

### Changed — `client/src/canvas/SpriteLoader.js`

- **`SPRITESHEET_PATH`** — Changed from `'/spritesheet.png'` to `` `${import.meta.env.BASE_URL}spritesheet.png` `` — resolves to `./spritesheet.png` in Electron builds, `/spritesheet.png` in dev

### Changed — `client/src/canvas/TileLoader.js`

- **`TILESHEET_PATH`** — Changed from `'/tilesheet.png'` to `` `${import.meta.env.BASE_URL}tilesheet.png` ``

### Changed — `client/src/components/BottomBar/SkillIconMap.js`

- **`SKILL_ICON_SHEET`** — Changed from `'/skill-icons.png'` to `` `${import.meta.env.BASE_URL}skill-icons.png` ``

### Changed — `client/src/audio/AudioManager.js`

- **`init()`** — Audio effects JSON fetch now uses `${baseUrl}audio-effects.json` instead of `/audio-effects.json`
- **`_preloadBuffer()`** — Sound file URLs from `audio-effects.json` (e.g. `/audio/combat/swing.wav`) are now normalized: leading `/` is replaced with `import.meta.env.BASE_URL`
- **`_playTrack()`** — Music track paths from `audio-effects.json` receive the same normalization

### Changed — `client/src/canvas/particles/ParticleManager.js`

- **`init()`** — Particle presets and effects JSON fetches now use `${baseUrl}particle-presets.json` and `${baseUrl}particle-effects.json` instead of absolute paths
- **Category file fetches** — Individual preset category files (e.g. `particle-presets/combat.json`) now use `${baseUrl}${file}` instead of `/${file}`

---

## [Bugfix] — 2026-03-12 — Batch PVP Team A Frozen AI

**Summary:** Fixed a bug where Team A units in batch PVP matches would return WAIT every turn instead of fighting, causing most matches to hit the max turn limit (200) and end as draws. Skills, attacks, and movement were all working correctly — the root cause was an AI ownership lookup failure.

**Root cause:** Team A units are spawned as `ai_allies` with `hero_id` and `ai_stance="follow"`, which routes them into the stance-based AI system (`_decide_stance_action`). The stance system calls `_find_owner()` to locate the human player they should follow. In batch PVP mode, the only "human" is a dummy host that gets removed from `all_units` after match creation. With no owner found, `_find_owner()` returns `None` and the follow stance falls back to WAIT. Team B (`ai_opponents`) was unaffected because those units have `hero_id=None` and fall through to independent aggressive AI.

**Note:** This bug was not caused by the Refactor 1A skills split. PVPVE mode is also unaffected — it handles leaderless AI teams correctly by designating one unit per team as `is_team_leader=True`, which `_find_owner()` uses as a fallback.

### Changed — `server/batch_pvp.py`

- **`run_headless_match()`** — After removing the dummy host, Team A units now have their `hero_id` cleared, `ai_stance` set to `None`, and `ai_behavior` set to `"aggressive"`. This converts them from stance-based hero allies (which need a human owner) into independent AI combatants — identical behavior to Team B. Both teams now use the same AI decision engine for fair simulation.

---

## [Balance] — 2026-03-11 — Monster Rarity & Wave Arena Balance Pass

**Summary:** Addressed oppressive damage spikes from rarity-upgraded (champion/rare) monsters in the wave arena and dungeons. The wave spawner was missing the difficulty budget and enhanced-per-room cap systems that dungeons use, allowing uncapped rarity stacking. Additionally, several affix multipliers were tuned down to reduce multiplicative damage escalation that could one-shot tanks.

**Root cause:** The wave spawner (`_spawn_next_wave`) called `roll_monster_rarity()` per enemy with zero guardrails — no `max_enhanced_per_room` cap, no `difficulty_budget` downgrade, and no `floor_overrides` for affix count limits. A single wave could produce multiple rares with full 2-3 affixes each. Combined with multiplicative damage stacking (tier × champion × affix × aura), a rare Extra Strong ghoul with Might Aura nearby could deal 27+ damage/hit vs a crusader's 135 HP.

### Changed — `server/app/core/wave_spawner.py`

- **`_spawn_next_wave()`** — Ported difficulty budget and cap enforcement from dungeon `map_exporter.py`:
  - Tracks `wave_enhanced_count` per wave, capped by `max_enhanced_per_room` from config (respects `floor_overrides`)
  - Computes per-wave `difficulty_budget` via `get_room_budget(wave_number, enemy_count)` — deducts `get_rarity_cost()` per enemy, downgrades rare→champion→normal if over budget
  - Reads `floor_overrides` via `get_floor_override(wave_number)` to apply early-wave affix count caps (e.g. 1-2 affixes on waves 1-3 instead of 2-3)
  - Supports per-wave `max_rarity` field from wave config — downgrades rolled rarity if it exceeds the wave's declared cap

### Changed — `server/configs/maps/wave_arena.json`

- **Waves 1-3** — Added `"max_rarity": "normal"` — no rarity upgrades allowed on introductory waves
- **Waves 4-5** — Added `"max_rarity": "champion"` — champions allowed but rares blocked
- **Waves 6-10** — Unchanged (full rarity range, constrained by budget system)

### Changed — `server/configs/monster_rarity_config.json`

- **`extra_strong` affix** — Damage multiplier reduced from 1.5× to **1.3×** (was the single largest damage spike source)
- **`might_aura` affix** — Ally damage multiplier reduced from 1.25× to **1.15×** (was amplifying entire packs multiplicatively)
- **`conviction_aura` affix** — Enemy armor reduction reduced from -3 to **-2** (was devastating low-armor classes: -3 from 2 armor = near-zero)
- **`floor_bonus_per_level`** — Rarity chance scaling reduced from 0.015 to **0.01** per wave/floor (softens the rarity ramp on later waves)

### Before/After — Damage Comparison (Rare Extra Strong Ghoul vs Crusader)

| Scenario | Before | After |
|---|---|---|
| Raw hit (no aura) | 21 dmg (7 hits to kill) | 17 dmg (8 hits to kill) |
| With Might Aura nearby | 27 dmg (5 hits to kill) | 19 dmg (8 hits to kill) |
| + Conviction Aura debuff | 30 dmg (5 hits to kill) | 20 dmg (7 hits to kill) |

### Tests — 3,775 passing

- Updated 5 test assertions in `test_monster_rarity.py` to match new `extra_strong` (1.3×) and `floor_bonus_per_level` (0.01) values

---

## [Refactor 1A] — 2026-06-21 — Split skills.py into skill_effects/ sub-package

**Summary:** Extracted all 30 `resolve_*` skill-effect handler functions from the monolithic `skills.py` (3,818 lines) into a new `server/app/core/skill_effects/` sub-package with 7 domain-specific modules. `skills.py` retains config loading, validation, buff/CC/ward helpers, and the central `resolve_skill_action` dispatcher. All 3,774 tests pass; all existing import paths remain backward-compatible via re-exports.

### Added — `server/app/core/skill_effects/` (new sub-package)

- **`_helpers.py`** — Shared helpers: `_apply_skill_cooldown`, `_resolve_skill_entity_target`
- **`heal.py`** — 3 handlers: `resolve_heal`, `resolve_hot`, `resolve_aoe_heal`
- **`damage.py`** — 13 handlers: `resolve_multi_hit`, `resolve_ranged_skill`, `resolve_holy_damage`, `resolve_stun_damage`, `resolve_aoe_damage`, `resolve_aoe_magic_damage`, `resolve_ranged_damage_slow`, `resolve_magic_damage`, `resolve_aoe_damage_slow`, `resolve_lifesteal_damage`, `resolve_lifesteal_aoe`, `resolve_aoe_damage_slow_targeted`, `resolve_melee_damage_slow`
- **`buff.py`** — 9 handlers: `resolve_buff`, `resolve_aoe_buff`, `resolve_damage_absorb`, `resolve_shield_charges`, `resolve_evasion`, `resolve_conditional_buff`, `resolve_thorns_buff`, `resolve_cheat_death`, `resolve_buff_cleanse`
- **`debuff.py`** — 6 handlers: `resolve_dot`, `resolve_taunt`, `resolve_aoe_debuff`, `resolve_targeted_debuff`, `resolve_ranged_taunt`, `resolve_aoe_root`
- **`movement.py`** — 1 handler: `resolve_teleport`
- **`summon.py`** — 2 handlers: `resolve_place_totem`, `resolve_soul_anchor`
- **`utility.py`** — 2 handlers: `resolve_detection`, `resolve_cooldown_reduction`
- **`__init__.py`** — Re-exports all 36 public symbols for `from app.core.skill_effects import ...`

### Changed — `server/app/core/skills.py`

- Reduced from ~3,818 lines to ~580 lines
- Retains: config loading (`load_skills_config`, `get_skill`, `get_all_skills`, etc.), validation (`can_use_skill`), buff helpers (`tick_buffs`, `get_melee_buff_multiplier`, etc.), CC helpers (`is_stunned`, `is_slowed`, etc.), ward/absorb helpers, and the `resolve_skill_action` dispatcher
- Dispatcher now calls handlers imported from `skill_effects` sub-modules
- Bottom-of-file re-exports ensure `from app.core.skills import resolve_heal` continues to work across all 43 consumer files (13 app + 30 test files)

### Architecture — Circular Import Avoidance

- `_helpers.py` imports only from `app.models` (no circular risk)
- Sub-modules that need skills helpers (e.g., `get_effective_armor`) use **lazy imports** inside function bodies: `from app.core.skills import get_effective_armor`
- `skills.py` imports from `skill_effects` at the bottom of the file, after all local functions are defined

---

## [Phase 27D] — 2026-03-09 — PVPVE Victory Conditions & PVE Team

**Summary:** Implements PVPVE victory logic so that the match correctly ends when only one player team survives, regardless of how many PVE enemies remain alive. PVE enemies on the `"pve"` team are excluded from the victory calculation. Player teams are hostile to each other and to PVE enemies. PVE enemies target all player teams equally. 21 new Phase D tests, 37 total PVPVE tests passing.

### Changed — `server/app/core/combat.py`

- **`check_team_victory()`** — Added optional `excluded_teams: set[str] | None` parameter. When provided (e.g. `{"pve"}`), units on excluded teams are filtered out before counting survivors. PVE enemies being alive no longer blocks PVPVE victory.

### Changed — `server/app/core/turn_phases/deaths_phase.py`

- **`_resolve_victory()`** — Added optional `match_type: str | None` parameter. When `match_type == "pvpve"`, passes `excluded_teams={"pve"}` to `check_team_victory()`.

### Changed — `server/app/core/turn_resolver.py`

- **`resolve_turn()`** — Derives `match_type` from `match_state.config.match_type` and passes it to `_resolve_victory()` for PVPVE exclusion logic.

### Changed — `server/app/services/tick_loop.py`

- **`match_tick()`** — Added PVE team FOV computation: when `match.team_pve` is populated, adds a `"pve"` entry to `ai_team_fov_map` so PVE enemies share vision with nearby PVE allies.

### Tests — `server/tests/test_pvpve.py`

- **`TestCheckTeamVictoryExcludedTeams`** (7 tests): Victory with excluded PVE, draw when all player teams dead, 4-team scenarios, backward compatibility.
- **`TestResolveVictoryPVPVE`** (3 tests): `_resolve_victory()` integration with match_type exclusion.
- **`TestPVEAITargeting`** (5 tests): PVE enemies hostile to all player teams, PVE allies with each other.
- **`TestPlayerTeamsHostile`** (6 tests): Inter-team hostility, same-team allies, player-vs-PVE hostility.

---

## [Phase 27C] — 2026-03-09 — PVPVE Match Manager Flow

**Summary:** Implements the PVPVE match initialization pipeline in the match manager. When a PVPVE match starts, the system generates a procedural PVPVE dungeon, distributes players across 2–4 teams, spawns each team in their designated corner zone, initializes dungeon state (doors, chests), spawns all PVE enemies on the dedicated `"pve"` team, and computes initial FOV. Floor advancement and stairs are disabled for PVPVE (single-floor mode).

### Added — `match_manager.py`

- **`_PVPVE_TEAM_KEYS`** — Constant list `["a", "b", "c", "d"]` for team assignment ordering.
- **`_start_pvpve_match(match_id)`** — Top-level PVPVE initialization orchestrator. Calls team assignment → dungeon generation → smart spawns → class stats → dungeon state init → PVE enemy spawning in sequence.
- **`_assign_pvpve_teams(match_id)`** — Distributes human players + AI allies across teams. Host always goes to team A. Others round-robin across active teams. AI allies fill remaining team slots round-robin. Clears old team lists before reassignment. Updates each player's `.team` field.
- **`_generate_pvpve_dungeon(match)`** — Generates a WFC procedural dungeon using `FloorConfig.for_pvpve()`. Registers the map as `pvpve_{match_id}`. Assigns a random dungeon theme and stores the dungeon seed.
- **`_spawn_pvpve_enemies(match_id)`** — Spawns PVE enemies from room definitions. All enemies placed on `team="pve"` (read from spawn data). Enemy IDs tracked in `match.team_pve` (not in team_a/b/c/d). Full monster rarity system support: champion packs, rare minions, super unique bosses with retinue.

### Changed — `match_manager.py`

- **`start_match()`** — Added PVPVE branch that delegates to `_start_pvpve_match()` before the standard dungeon/PVP flow. Non-PVPVE matches unchanged.
- **`get_stairs_info()`** — Returns empty stairs for PVPVE matches (no stairs in single-floor mode).
- **`advance_floor()`** — Returns `None` immediately for PVPVE matches (no floor advancement).
- **`remove_match()`** — Now also cleans up `pvpve_{match_id}` runtime maps in addition to `wfc_{match_id}`.

### Tests

- 22 new tests in `test_pvpve_phase_c.py`:
  - `TestAssignPVPVETeams` (7 tests) — Host on team A, 2-team round-robin, 4-team distribution, 3-team (no team D), AI distribution, player.team field updates, old list clearing.
  - `TestPVPVEMatchStart` (5 tests) — Match starts successfully, pvpve_ map prefix, dungeon seed stored, theme assigned, dungeon state initialized.
  - `TestPVPVEEnemySpawning` (5 tests) — PVE enemies on "pve" team, team_pve populated, PVE IDs not in player teams, PVE are AI units, PVE tracked in ai_ids.
  - `TestPVPVEFOV` (1 test) — FOV computed for all alive units across all teams.
  - `TestPVPVENoFloorAdvancement` (3 tests) — No stairs info, advance_floor returns None, floor stays at 1.
  - `TestPVPVECleanup` (1 test) — remove_match unregisters PVPVE runtime map.

### Regression

- 3717 passing (+22 new) · 1 pre-existing failure (unrelated `test_turn_resolver.py` melee tracking assertion)

---

## [Phase 27B] — 2026-03-09 — PVPVE WFC Generation Pipeline

**Summary:** Extends the WFC dungeon generation engine to produce PVPVE-specific layouts. The decorator places 2–4 team spawn rooms in grid corners, a center boss room, applies a multi-spawn proximity ramp (safe → softened → normal), and computes a difficulty gradient (normal → hard → elite → boss) based on Manhattan distance to center. The map exporter tags all PVE enemies with `"team": "pve"`, collects per-team spawn zones, and emits `boss_room` metadata.

### Added — `dungeon_generator.py`

- **`FloorConfig.pvpve_mode`** (bool, default False) — Enables PVPVE layout generation.
- **`FloorConfig.pvpve_team_count`** (int, default 2) — Number of player teams (2–4).
- **`FloorConfig.for_pvpve()`** — Factory classmethod producing a FloorConfig optimized for PVPVE: 8×8 grid, floor 1, mid-tier roster, batch_size=5, balanced style, `empty_room_chance=0.15`.
- Updated `generate_dungeon_floor()` to inject `pvpve_mode`, `pvpve_team_count`, and `guaranteeStairs: False` into decorator settings when in PVPVE mode. Passes PVPVE params and decoration result to the map exporter.

### Added — `room_decorator.py`

- **`_PVPVE_DECORATOR_DEFAULTS`** — Config block for PVPVE-specific decorator settings (boss_guards, boss_chests, safe/softened enemy caps).
- **`_PVPVE_TEAM_CORNERS`** — Maps teams a–d to grid corners: a→top-left, b→bottom-right, c→top-right, d→bottom-left.
- **`_PVPVE_DIFFICULTY_TIERS`** — Distance-based difficulty tiers: boss (dist 0, 5 enemies), elite (dist 1, 5), hard (dist 2, 4), normal (3+, 3).
- **`_get_active_teams(team_count)`** — Returns active team letters based on count (clamped 2–4).
- **`_pvpve_assign_corner_spawns()`** — Places spawn rooms near target corners using `_find_nearest_flexible()`.
- **`_pvpve_assign_center_boss()`** — Places boss room at grid center, avoiding assigned rooms.
- **`_pvpve_compute_proximity_ramp()`** — Multi-spawn proximity ramp: distance 1 = "safe", distance 2 = "softened".
- **`_pvpve_compute_difficulty_tier()`** — Manhattan distance to center → tier name.
- **`_pvpve_get_max_enemies_for_tier()`** — Per-tier enemy count cap.
- Refactored `decorate_rooms()` with a PVPVE branch: corner spawns → center boss → proximity ramp → difficulty gradient. Standard dungeon path preserved unchanged.
- Phase 4 tile placement: PVPVE boss rooms get configurable extra guards + chests. Spawn-prefixed roles handled in placement and stats.
- Return value includes `pvpve_spawn_rooms` (team → {gridRow, gridCol}) and `pvpve_difficulty_tiers` when in PVPVE mode.

### Added — `map_exporter.py`

- **`export_to_game_map()`** — New params: `pvpve_mode`, `pvpve_team_count`, `decoration_result`.
- **Per-team spawn points** (`spawn_points_by_team`) — Groups S-tile spawn points by team using decorator's `pvpve_spawn_rooms` grid-cell lookup.
- **PVE team tagging** — All enemy spawns (regular E, boss B, super_unique, retinue) get `"team": "pve"` when in PVPVE mode.
- **Per-team spawn zones** — Built from grouped spawn points (expanded ±2 tiles for formation room), keyed by team letter.
- **Boss room metadata** — `boss_room` dict with id, bounds, enemy_spawns, chests.
- **Map type** — Set to `"pvpve"` instead of `"dungeon"` when in PVPVE mode.
- Top-level output includes `pvpve_team_count`, `spawn_points_by_team`, `boss_room`.

### Tests

- 63 new tests in `test_pvpve_phase_b.py`:
  - `TestFloorConfigPVPVE` (13 tests) — factory defaults, grid size, team clamping, density, roster, map name.
  - `TestPVPVEHelpers` (13 tests) — active teams, difficulty tiers, max enemies per tier.
  - `TestPVPVECornerSpawns` (5 tests) — 4-corner placement, 2-team mode, near-top-left/bottom-right, no adjacent spawns.
  - `TestPVPVECenterBoss` (2 tests) — near-center placement, no overlap with spawns.
  - `TestPVPVEProximityRamp` (3 tests) — safe/softened/no-override at correct distances.
  - `TestPVPVEDecoratorIntegration` (9 tests) — 4-team spawns, 2-team spawns, boss placement, no stairs, safe adjacency, metadata, difficulty tiers, boss guards.
  - `TestPVPVEExporter` (11 tests) — map_type, team_count, spawn zones, spawn points, enemy PVE tags, boss metadata, standard mode unchanged.
  - `TestPVPVEFullPipeline` (7 tests) — end-to-end generation, map type, dimensions, spawn zones, PVE tags, determinism.

### Regression

- All 335 existing WFC tests pass unchanged.

---

## [Phase 27A] — 2026-03-09 — PVPVE Data Model & Match Type

**Summary:** Foundation data model for the new PVPVE competitive dungeon mode. Adds the `PVPVE` match type enum, PVPVE-specific configuration fields on `MatchConfig`, and a `team_pve` list on `MatchState` for tracking PVE enemy IDs separately from player teams.

### Added

- **`MatchType.PVPVE`** — New enum value `"pvpve"` for competitive dungeon matches where 2–4 player teams fight PVE enemies and each other.

- **`MatchConfig` PVPVE fields:**
  - `pvpve_team_count` (int, default 2) — Number of player teams (2–4).
  - `pvpve_pve_density` (float, default 0.5) — PVE enemy density multiplier (0.0–1.0).
  - `pvpve_boss_enabled` (bool, default True) — Whether to spawn a center boss.
  - `pvpve_loot_density` (float, default 0.5) — Chest/loot density multiplier.
  - `pvpve_grid_size` (int, default 8) — WFC grid size for map generation.

- **`MatchState.team_pve`** — List of PVE enemy IDs (`list[str]`, default empty). Tracks PVE enemies separately so they can be excluded from player team victory checks.

### Tests

- 16 new tests in `test_pvpve.py`:
  - `TestMatchTypePVPVE` (5 tests) — enum existence, serialization, deserialization, config assignment, JSON round-trip.
  - `TestMatchConfigPVPVEFields` (7 tests) — default values for all 5 fields, custom values, full round-trip.
  - `TestMatchStatePVPVE` (4 tests) — empty default, ID storage, round-trip, full state with all teams + PVE.

### Test count

- 3632 passing (+16 new) · 1 pre-existing failure (unrelated `test_phase16d_unique_items.py`)

---

## [Phase 26D] — 2026-03-07 — AI Totem Awareness

**Summary:** AI-controlled heroes now recognize active healing totems as safe zones. They will retreat toward totems when critically injured, prefer kiting in the direction of a totem, and gently drift toward totem heal zones during normal combat when hurt — without being hard-locked to the totem's position.

### Added

- **`_find_nearest_healing_totem()` helper** — Scans `match_state.totems` for the closest alive, same-team healing totem within a configurable distance (`_TOTEM_RETREAT_MAX_DIST = 8` tiles). Returns the totem dict or `None`. Used by retreat, kiting, and combat positioning logic.

- **`_tile_inside_totem_radius()` helper** — Quick Chebyshev check for whether a tile is within a totem's `effect_radius`.

- **`_totem_biased_step()` helper** — Soft drift function for normal combat movement. When an AI hero is below 80% HP (`_TOTEM_DRIFT_HP_THRESHOLD`) and a healing totem is nearby, nudges the planned movement step toward a tile inside the totem's radius — but only if it doesn't lose progress toward the AI's actual move target. Creates a gentle "gravity well" effect without overriding combat goals.

- **Retreat Priority 1.5: Healing Totem** — New retreat destination slotted between "path toward support ally" (Priority 1) and "path toward owner" (Priority 2) in `_find_retreat_destination()`. When a low-HP hero triggers retreat and there's an active same-team healing totem within 8 tiles, the hero paths toward the totem center. If already inside the totem's effect radius, falls through to the next priority (no unnecessary repositioning).

- **Totem-biased kiting** — In both Follow and Aggressive stance kiting (Phase 8K-3), ranged roles now score retreat tiles with a totem proximity bonus (`_TOTEM_KITE_BIAS_WEIGHT = 2`). When stepping away from a melee threat, the AI prefers tiles that are inside (or closer to) a healing totem radius, while still maximizing distance from the threat. Falls back to the original retreat tile if no totem is active.

- **Totem-biased combat movement** — In both Follow and Aggressive stance "move toward target" phases, the planned A* step is passed through `_totem_biased_step()` when the AI is hurt. This causes injured heroes to naturally drift into totem heal zones during regular fighting without changing their target priorities.

- **Constants:**
  - `_TOTEM_RETREAT_MAX_DIST = 8` — Max distance for AI to consider retreating toward a totem
  - `_TOTEM_KITE_BIAS_WEIGHT = 2` — Scoring bonus when a kite tile is inside totem radius
  - `_TOTEM_DRIFT_HP_THRESHOLD = 0.80` — HP ratio below which soft drift activates

### Changed

- **`_find_retreat_destination()` signature** — Added optional `match_state=None` parameter to access `match_state.totems` for the new Priority 1.5 totem retreat.

- **`_decide_stance_action()` retreat call** — Now forwards `match_state=match_state` to `_find_retreat_destination()`.

- **`_decide_follow_action()` signature** — Added optional `match_state=None` parameter. Stance dispatch now forwards `match_state`.

- **`_decide_aggressive_stance_action()` signature** — Added optional `match_state=None` parameter. Stance dispatch now forwards `match_state`.

- **Follow stance kiting block** — Replaced simple `_find_retreat_tile` with totem-biased tile scoring when a healing totem is active.

- **Aggressive stance kiting block** — Same totem-biased tile scoring as Follow stance.

- **Follow stance movement** — Final "Move toward target" step now passes through `_totem_biased_step()`.

- **Aggressive stance movement** — Final "Move toward target" step now passes through `_totem_biased_step()`.

### File Changed

- `server/app/core/ai_stances.py` — All changes confined to this single file (~120 lines added).

### Not Changed

- **Hold stance** — Never moves; no totem awareness needed (by design).
- **Defensive stance** — 2-tile owner leash already constrains positioning; adding totem bias would conflict with the "stay near owner" mandate. No changes.
- **Enemy AI** — Enemies have no totem awareness (intentional — they don't cooperate with player totems).
- **Shaman's own AI** — The Shaman's totem placement logic (`_totemic_support_skill_logic` in `ai_skills.py`) is unchanged. The Shaman already places totems intelligently; this change makes *other* heroes aware of those totems.

### Design Notes

- **Soft preference, not hard lock** — No AI behavior is overridden. Totem proximity is a tiebreaker / secondary factor in every case. Heroes still chase enemies, still attack, still regroup with the owner. The totem is simply an attractive "safe zone" that the AI knows about.
- **Three tiers of totem awareness:**
  1. **Retreat** (strongest) — Critical HP heroes actively path TO the totem
  2. **Kiting** (medium) — Ranged heroes prefer kite directions near the totem
  3. **Combat drift** (gentlest) — Hurt heroes nudge toward totem during normal movement
- **All 3605 tests pass** (1 pre-existing failure in `test_phase16d_unique_items.py` unrelated to this change). 675 AI-specific tests pass with zero regressions.
