# Progression Systems Brainstorm

**Status:** Brainstorm / Pre-Design  
**Date:** March 17, 2026  
**Goal:** Add meaningful progression layers without undermining permadeath or the loot-driven core loop.

---

## Design Principles

- Permadeath stays. It's the game's identity — every dungeon run has real stakes.
- Progression should make deaths *sting* without making them *devastating*.
- Gear remains the primary power driver. New systems complement it, not replace it.
- Every run should move the player forward in some way, even failed ones.
- Avoid illusion-of-choice traps (e.g., stat point allocation that resolves to one obvious build per class).

---

## 1. Hero Milestones

**Concept:** Heroes that survive multiple runs become visibly more prestigious and gain small, meaningful perks. Uses existing `matches_survived` and `enemies_killed` tracking.

### Milestone Tiers

| Tier | Title | Requirement | Reward |
|------|-------|-------------|--------|
| 0 | Recruit | Hired | Baseline |
| 1 | Blooded | 5 kills | Title + portrait border |
| 2 | Veteran | 3 matches survived | +1 inventory slot (11 total) |
| 3 | Elite | 15 kills + 5 matches | +2% to all resists (minor survivability) |
| 4 | Champion | 30 kills + 10 matches | Unlocks a 4th equipment slot (trinket/charm) |
| 5 | Legend | 50 kills + 20 matches | Hero name rendered in gold, minor stat perk |

### Design Notes

- Thresholds are rough — need to playtest what "feels right" for how fast heroes tier up.
- A 4th equipment slot at Champion tier is the biggest power spike. Ties into existing gear systems naturally.
- Legend heroes create interesting risk/reward tension: powerful but terrifying to deploy.
- Visual distinction (borders, gold names, titles) gives progression *feel* even before mechanical rewards kick in.
- Consider: show milestone progress on the hero roster panel (e.g., "12/15 kills to Elite").
- Consider: death screen could highlight what milestone tier was lost — makes permadeath hit harder emotionally.

---

## 2. Equipment Identity — Role-Weighted Gear

**Problem:** Higher rarity items almost always have more total stats than lower rarity. Players equip any yellow/purple drop without thinking about whether the stats actually fit their build. Gear doesn't feel like a meaningful choice.

### Option A: Role-Weighted Affixes (Preferred Direction)

Tag base item types with a `role_affinity` that biases which affixes can roll on them.

| Role | Stat Emphasis | Classes That Benefit Most |
|------|--------------|---------------------------|
| Frontline | +HP, +armor, +thorns, +damage_reduction | Crusader, Revenant, Blood Knight |
| Striker | +melee_damage, +crit, +crit_damage, +armor_pen | Blood Knight, Hexblade, Crusader |
| Marksman | +ranged_damage, +crit, +ranged_range | Ranger, Inquisitor |
| Caster | +skill_damage, +magic_damage, +cooldown_reduction | Mage, Plague Doctor, Bard, Shaman |
| Healer | +heal_power, +hp_regen, +cooldown_reduction | Confessor, Shaman, Bard |

**Key:** Any class can wear any role's gear. A Mage in Frontline armor is making a *survival choice* — and that's the point. A Magic-tier Caster Staff with perfect affixes should be a legitimate competitor against a Rare-tier Frontline Axe with scattered stats for a Mage player.

### Option B: Item Power Score

Add a visible "Item Power" number derived from total stat value. Helps players compare items at a glance and reveals when a lower-rarity item with build-appropriate affixes is actually stronger for them than a higher-rarity item with irrelevant stats.

### Option C: Affix Synergy Bonuses

If an item rolls 2+ affixes in the same stat family, it gets a small synergy bonus:
- Two crit affixes → "+Critical Synergy: +3% crit chance"
- Two survival affixes → "+Fortified: +5% damage reduction"

Makes affix combinations feel more interesting. Players look for stat combos instead of just raw numbers.

### Notes

- Options A, B, and C are not mutually exclusive — they layer well together.
- Role affinity doesn't need to be a hard lock on the affix pool. Could be a weighting system: Frontline armor has 3x chance to roll tank affixes but *can* still roll caster affixes rarely. This creates excitement when a Caster Robe rolls +armor by chance.
- Need to be careful that role tags don't make loot feel *less* exciting. The "wrong role" drop should still have a use case (sell it, bank it for another hero, etc.).

---

## 3. Account-Level Progression

**Concept:** The player's account progresses even when individual heroes die. Failed runs still contribute to long-term unlocks. Makes the game feel like it respects the player's time.

### Tracking Fields (New on PlayerProfile)

- `total_heroes_lost` — cumulative permadeaths
- `deepest_floor_reached` — highest dungeon floor ever reached
- `total_gold_earned` — lifetime gold (not current balance)
- `total_enemies_killed` — across all heroes, all time
- `sets_completed` — number of distinct full sets equipped at least once

### Account Milestones (Brainstorm)

| Category | Milestone | Unlock |
|----------|-----------|--------|
| **Losses** | Lost 5 heroes | Tavern heroes start with 1 random Magic item equipped |
| **Losses** | Lost 15 heroes | Tavern heroes can roll +5% higher base stat variance |
| **Depth** | Reached floor 5 | Merchant occasionally stocks Rare items |
| **Depth** | Reached floor 8 | "Veteran Tavern" — hire heroes with guaranteed higher stat rolls |
| **Economy** | Earned 1,000g total | Bank size +10 slots |
| **Economy** | Earned 5,000g total | Merchant sell prices +20% |
| **Kills** | 100 total enemy kills | Potential class unlock trigger (if classes are gated) |
| **Kills** | 500 total kills | All heroes earn +10% gold find |
| **Sets** | Completed any full set | Set piece drop weights +50% globally |
| **Survival** | A hero survived 10 runs | Unlock "Heirloom" system (see below) |

### Design Notes

- Milestone unlocks should feel like the *world* is responding to the player's experience, not just numbers going up.
- Losses-based milestones are critical — they reframe death from "I lost everything" to "I'm getting closer to an unlock." This is the anti-frustration layer.
- Floor-depth milestones gate merchant/tavern quality and give players a reason to push deeper even if they're not confident they'll survive.
- Consider: surface account milestones on the Town Hub screen. A visible progression track that fills over time.
- Consider: some milestones could unlock cosmetic themes for the town or UI (grimdark variants, banners, etc.).

---

## 4. Heirloom System

**Concept:** When a hero dies, their single best item is preserved and sent to the player's bank instead of being destroyed with everything else.

### Rules

- Gated behind an account milestone (e.g., "a hero has survived 10 runs").
- Only 1 item saved per death — the highest-value equipped item (by item power or rarity).
- The heirloom item gets a visual tag ("Heirloom of [dead hero name]") — narrative flavor.
- Does NOT save inventory items, only the one equipped piece.
- Possible limit: heirloom bank cap (e.g., 5 heirloom slots) to prevent hoarding.

### Why This Matters

- Transforms death from "total wipe" to "painful but not devastating."
- Creates emergent storytelling: "This sword belonged to my Crusader before he fell on floor 7. Now my new Ranger carries it."
- Encourages players to push deeper with geared heroes instead of hoarding them in safety, because even death preserves *something*.

### Open Questions

- Should heirlooms gain a small bonus for being inherited? ("Tempered by loss: +2% damage")
- Should there be a gold cost to claim the heirloom from the bank?
- Could heirlooms have a visual glow/effect to distinguish them?

---

## Priority / Effort Estimate

| System | Impact | Effort | Dependencies |
|--------|--------|--------|-------------|
| Hero Milestones | High feel-good, moderate power | Low — data already tracked, needs milestone checks + UI | None |
| Role-Weighted Gear | Solves biggest gear pain point | Medium — tag items, adjust affix pool in generator | None |
| Account Milestones | Makes whole game feel more forgiving | Medium — new profile fields, milestone tracker, town UI | None |
| Heirloom System | Psychologically huge for permadeath acceptance | Low-Medium — death handler change, bank UI, heirloom tag | Account Milestones (gating) |
| Item Power Score | QoL / comparison clarity | Low — pure calculation + UI display | None |
| Affix Synergy Bonuses | Loot excitement / depth | Medium — synergy detection in generator, tooltip display | Role-Weighted Gear (pairs well) |

---

## Open Questions for Future Discussion

- Should any of these systems apply to PvP arena matches, or dungeon-only?
- How do hero milestones interact with the Arena Analyst tool? (Track milestone distribution across matches?)
- Should account milestones ever be losable / resettable (seasonal resets for competitive play)?
- Could hero milestones feed into a "Hall of Fame" for dead Legend-tier heroes? (Memorial wall in town)
- How visible should account progression be to other players in multiplayer lobbies?
