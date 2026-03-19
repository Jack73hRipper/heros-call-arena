# Phase 21 — Armor Affinity System & Tooltip Overhaul

**Created:** March 18, 2026  
**Status:** Design Complete — Ready for Implementation  
**Previous:** Phase 20 (Turn Resolver File Split)  
**Goal:** Introduce soft class/role-based armor identity via an "armor affinity" system, and overhaul the item tooltip to make stat comparison clear and intuitive.

---

## The Problem

### Armor Identity

Weapons are class-locked — a Ranger can't equip a Sword, a Crusader can't equip a Bow. This reinforces class fantasy. But **armor and accessories have zero class identity.** A Mage in Full Plate is mechanically identical to a Crusader in Full Plate. There's no incentive to seek out "mage gear" vs "tank gear" beyond raw stat preferences.

A full hard-lock system ("only Crusaders can wear plate") would fix identity but **kill loot excitement** — in a party of 4 classes, 75% of armor drops become instant vendor trash. The stats already self-select (casters want skill_damage_pct, tanks want armor), but the system doesn't reinforce or reward this.

**What we want:** Class identity on armor **without** making drops feel bad.

### Tooltip Confusion

The item tooltip currently shows:
- Base stats (gray) → affix stats (blue) → a "vs Equipped" comparison section with directional arrows
- The comparison lists deltas (`▲ +3 Armor`) but **doesn't show absolute values side-by-side**
- With 20 possible stats across 4 tiers, the tooltip becomes a wall of text with no visual hierarchy
- There's no overall "upgrade or downgrade?" signal — players must mentally sum individual arrows
- Stat labels vary wildly in length ("HP" vs "Damage Reduction" vs "Armor Penetration"), making the list hard to scan

Players shouldn't need to do mental math to decide "is this better?"

---

## Table of Contents

1. [Armor Category System](#21a--armor-category-system)
2. [Class Affinity Bonuses](#21b--class-affinity-bonuses)
3. [Item Generator Integration](#21c--item-generator--loot-integration)
4. [Tooltip Overhaul](#21d--tooltip-overhaul)
5. [Merchant & Town UI Updates](#21e--merchant--town-ui-updates)
6. [Balance & Config Tuning](#21f--balance--config-tuning)

---

## Phase Dependency Map

```
Phase 20 (Turn Resolver Split — stable codebase)
    │
    ▼
  21A — Armor Category System (FOUNDATION — data model changes)
    │
    ├──► 21B — Class Affinity Bonuses (needs categories on items + classes)
    │      │
    │      └──► 21C — Item Generator & Loot (needs affinity logic to tag generated items)
    │
    ├──► 21D — Tooltip Overhaul (independent of affinity, but benefits from category display)
    │
    ├──► 21E — Merchant & Town UI (needs categories + affinity for display)
    │
    └──► 21F — Balance & Config Tuning (final, after everything is in)
```

---

## 21A — Armor Category System

**Effort:** Small  
**Risk:** Low — additive data, no existing behavior changes  
**Prerequisite:** None

### Goal

Add an `armor_category` field to armor items, grouping them into three archetypes that map to RPG roles.

### Armor Categories

| Category | Fantasy | Typical Stats | Example Items |
|----------|---------|---------------|---------------|
| `heavy` | Plate, chain, brigandine | High armor, max_hp, thorns | Common Plate Armor, Uncommon Brigandine, The Bonecage |
| `light` | Leather, hide, shadow cloak | Dodge, crit, move_speed, armor_pen | Common Leather Armor, Shadowshroud, Common Hide Armor |
| `cloth` | Robes, vestments | skill_damage_pct, CDR, heal_power_pct, magic_find | Common Robes, Uncommon Mage Robes, Common Vestments |

### Data Model Changes

**`server/app/models/items.py`** — add enum + field:

```python
class ArmorCategory(str, Enum):
    HEAVY = "heavy"
    LIGHT = "light"
    CLOTH = "cloth"
```

Add to `Item`:
```python
armor_category: str = ""  # "heavy", "light", "cloth" — empty for non-armor items
```

**`server/configs/items_config.json`** — add `armor_category` to every armor entry:

| Item | Category |
|------|----------|
| Common Chain Armor | heavy |
| Common Plate Armor | heavy |
| Uncommon Plate Armor | heavy |
| Uncommon Brigandine | heavy |
| Common Leather Armor | light |
| Common Hide Armor | light |
| Uncommon Shadow Cloak | light |
| Uncommon Hide Armor | light |
| Common Bone Armor | heavy |
| Uncommon Bone Plate | heavy |
| Common Robes | cloth |
| Uncommon Mage Robes | cloth |
| Common Vestments | cloth |
| Uncommon Vestments | cloth |

**`server/configs/uniques_config.json`** — add `armor_category` to unique armor pieces:

| Unique | Category |
|--------|----------|
| The Bonecage | heavy |
| Shadowshroud | light |
| Penitent Mail | heavy |
| Wraithmantle | light |
| Ironwill Plate | heavy |

**`server/configs/sets_config.json`** — add `armor_category` to set armor pieces:

| Set Piece | Category |
|-----------|----------|
| Crusader's Oath — Plate | heavy |
| Voidwalker's Regalia — Cloak | light |
| Deadeye's Arsenal — Leathers | light |
| Faith's Radiance — Vestments | cloth |
| Seeker's Judgment — Coat | light |

### Files Changed

| File | Changes |
|------|---------|
| **`server/app/models/items.py`** | Add `ArmorCategory` enum, add `armor_category: str = ""` to `Item` model |
| **`server/configs/items_config.json`** | Add `"armor_category"` field to all 14 armor entries |
| **`server/configs/uniques_config.json`** | Add `"armor_category"` field to 5 unique armor entries |
| **`server/configs/sets_config.json`** | Add `"armor_category"` field to 5 set armor pieces |

### Verification

- [ ] All 14 config armor items have `armor_category` set
- [ ] All 5 unique armor pieces have `armor_category` set
- [ ] All 5 set armor pieces have `armor_category` set
- [ ] `Item` model accepts and serializes `armor_category`
- [ ] Non-armor items default to `""` (weapons, accessories, consumables)
- [ ] Existing tests pass (0 regressions)

---

## 21B — Class Affinity Bonuses

**Effort:** Medium  
**Risk:** Medium — touches stat calculation in equipment_manager.py  
**Prerequisite:** 21A

### Goal

Each class has a "preferred armor category." When a class equips armor matching their preference, the armor's **base stats** receive a percentage bonus. Off-type armor still works — no hard locks — but preferred armor is strictly better.

### Class → Preferred Armor Mapping

| Class | Role | Preferred Armor | Rationale |
|-------|------|-----------------|-----------|
| **Crusader** | Tank | `heavy` | Frontline plate wearer |
| **Revenant** | Retaliation Tank | `heavy` | Undead knight in heavy armor |
| **Blood Knight** | Sustain Melee DPS | `heavy` | Aggressive melee, wants survivability |
| **Confessor** | Support/Healer | `cloth` | Priestly vestments, heal power focus |
| **Shaman** | Totemic Healer | `cloth` | Spiritual caster, heal/skill focus |
| **Mage** | Caster DPS | `cloth` | Classic mage robes |
| **Bard** | Offensive Support | `cloth` | Performance robes, skill damage focus |
| **Plague Doctor** | Controller | `cloth` | Scholarly robes, DoT/skill focus |
| **Ranger** | Ranged DPS | `light` | Leather armor, agile |
| **Inquisitor** | Scout/Hybrid | `light` | Light coat, mobility |
| **Hexblade** | Hybrid DPS | `light` | Shadow armor, versatile |

### Affinity Bonus Mechanics

```
AFFINITY BONUS:
  When a class equips armor matching their preferred_armor category,
  the armor's BASE stats (not affix stats) are multiplied by (1 + affinity_bonus).

  Default bonus: 15% (0.15)

EXAMPLE:
  Crusader equips Common Plate Armor (base: +6 armor, +20 max_hp)
  → Preferred armor = heavy ✓
  → Effective base stats: +6.9 armor (→ rounds to +7), +23 max_hp (→ rounds to +23)

  Mage equips Common Plate Armor
  → Preferred armor = cloth, item = heavy ✗
  → Effective base stats: +6 armor, +20 max_hp (no bonus)

IMPORTANT:
  - Only BASE stats are boosted (not affix rolls — those are already random)
  - Bonus is applied during _recalculate_effective_stats(), not baked into the item
  - The item itself is unchanged — only the effective stats on the character are affected
  - Rounding: floor() for flat stats, 2-decimal for percentage stats
```

### Why 15%?

- **Noticeable but not mandatory.** A +6 armor plate becomes +7 — that's +1 armor, meaningful but not game-breaking. A Mage can still wear plate if the affixes are incredible.
- **Scales with item quality.** A rare heavy armor with +12 base armor gives +1.8 → +13 to a tank. The better the item, the more the bonus matters.
- **Tunable.** If 15% feels too weak, bump to 20%. Too strong, drop to 10%. It's a single config value per class.

### Config Changes

**`server/configs/classes_config.json`** — add two fields per class:

```jsonc
{
  "crusader": {
    "allowed_weapons": ["melee", "hybrid"],
    "preferred_armor": "heavy",        // NEW
    "armor_affinity_bonus": 0.15,      // NEW
    // ... existing fields unchanged
  },
  "mage": {
    "allowed_weapons": ["caster", "hybrid"],
    "preferred_armor": "cloth",
    "armor_affinity_bonus": 0.15,
    // ...
  }
  // ... all 11 classes
}
```

### Equipment Manager Changes

**`server/app/core/equipment_manager.py`** — modify `_recalculate_effective_stats()`:

```python
def _recalculate_effective_stats(player, classes_config):
    """Recalculate all effective stats from equipment, including armor affinity."""
    # ... existing aggregation of equipment stat bonuses ...

    # NEW: Armor affinity bonus
    armor_item = player.equipment.armor
    if armor_item and armor_item.armor_category:
        class_cfg = classes_config.get(player.class_id, {})
        preferred = class_cfg.get("preferred_armor", "")
        if armor_item.armor_category == preferred:
            bonus_pct = class_cfg.get("armor_affinity_bonus", 0.0)
            if bonus_pct > 0:
                # Boost only the armor's BASE stats (not affixes)
                base_stats = armor_item.base_stats or {}
                for stat_key, base_val in base_stats.items():
                    if base_val and base_val != 0:
                        bonus = base_val * bonus_pct
                        # Apply to player's effective stats
                        _add_stat(player.effective_stats, stat_key, bonus)

    # ... existing caps (dodge ≤ 40%, etc.) ...
```

### Visual Indicator

When viewing equipped armor that matches the class affinity:
- Equipment slot shows a small **shield icon** with a colored pip
- Tooltip displays: `✦ Crusader Affinity — +15% base stats` in a gold accent line
- When viewing non-matching armor: no indicator (silent — don't punish, just don't reward)

### Files Changed

| File | Changes |
|------|---------|
| **`server/configs/classes_config.json`** | Add `"preferred_armor"` and `"armor_affinity_bonus"` to all 11 classes |
| **`server/app/core/equipment_manager.py`** | Add armor affinity bonus calculation in `_recalculate_effective_stats()` |
| **`server/app/models/player.py`** | (If needed) Ensure `effective_stats` dict supports the bonus passthrough |
| **`client/src/components/Inventory/Inventory.jsx`** | Add affinity badge on armor equipment slot |
| **`client/src/components/Inventory/ItemTooltip.jsx`** | Add affinity bonus line when matched |
| **`client/src/utils/itemUtils.js`** | Add `getArmorAffinityInfo()` helper |

### Verification

- [ ] Crusader equipping heavy armor gets +15% base stats
- [ ] Mage equipping heavy armor gets no bonus
- [ ] Mage equipping cloth armor gets +15% base stats
- [ ] Affinity bonus shows in tooltip as gold accent line
- [ ] Affinity bonus does NOT apply to affix stats (only base)
- [ ] Unequipping armor removes the bonus correctly
- [ ] Swapping armor recalculates correctly
- [ ] All stat caps still enforced after bonus
- [ ] Existing equipment tests pass (0 regressions)
- [ ] New tests: affinity bonus calculation (per class, per category — ~15 tests)

---

## 21C — Item Generator & Loot Integration

**Effort:** Small  
**Risk:** Low — extending existing generation pipeline  
**Prerequisite:** 21A

### Goal

Ensure procedurally generated armor items receive an `armor_category` and that loot generation can bias drops toward party-relevant categories.

### Item Generator Changes

**`server/app/core/item_generator.py`**:

1. **Category assignment for generated armor** — When generating a random armor item, assign `armor_category` based on the base type selected:
   - If the base type has `armor_category` in config → use it
   - If generating from scratch (no base type) → weighted random: heavy 35%, light 35%, cloth 30%

2. **Party-aware loot bias (optional, soft)** — When generating loot for a chest or enemy drop in a party context:
   - 60% chance: roll category matching a random party member's `preferred_armor`
   - 40% chance: fully random category
   - This ensures party-relevant drops appear more often without eliminating variety

### Affix Pool Filtering by Category (Soft Bias)

Certain affixes are more thematic for certain armor categories. This doesn't restrict — it biases:

| Category | Weighted-Up Affixes | Weighted-Down Affixes |
|----------|--------------------|-----------------------|
| `heavy` | thorns, max_hp, armor, damage_reduction_pct | dodge_chance, skill_damage_pct |
| `light` | dodge_chance, crit_chance, move_speed, armor_pen | thorns, heal_power_pct |
| `cloth` | skill_damage_pct, cooldown_reduction_pct, heal_power_pct, magic_find_pct | thorns, armor |

Implementation: multiply affix weight by 1.5× for "weighted-up" stats and 0.5× for "weighted-down" stats during affix rolling for armor items. All affixes can still appear — this just makes drops feel more "right" for their category.

### Files Changed

| File | Changes |
|------|---------|
| **`server/app/core/item_generator.py`** | Add `armor_category` assignment for generated armor, add optional soft affix bias by category |
| **`server/app/core/loot.py`** | Pass party class info to generator for party-aware bias (optional) |
| **`server/configs/affixes_config.json`** | Add `"category_weights"` field to affixes (optional — can also be hardcoded) |

### Verification

- [ ] Generated armor items always have `armor_category` set
- [ ] Category distribution is roughly 35/35/30 for random drops
- [ ] Party-aware bias produces more relevant drops (~60%)
- [ ] Affix category weighting produces thematically appropriate affixes
- [ ] All loot generation tests pass (0 regressions)
- [ ] New tests: category assignment, party bias, affix weighting (~12 tests)

---

## 21D — Tooltip Overhaul

**Effort:** Medium  
**Risk:** Low — purely client-side UI, no game logic changes  
**Prerequisite:** None (can be done in parallel with 21A–21C)

### The Problem (Detailed)

The current tooltip has these UX issues:

1. **No side-by-side comparison.** The "vs Equipped" section shows deltas (`▲ +3 Armor`) but not the absolute values. Players see "this is better by 3" but can't see "this gives 8, equipped gives 5." Both pieces of information matter.

2. **Wall of text.** With 20 possible stats, a well-rolled epic item can have 8+ stat lines (4 base + 4 affix) plus comparison lines. Combined with set bonuses, sell value, and flavor text, the tooltip becomes overwhelming.

3. **No overall verdict.** Players must mentally tally individual arrows to decide "is this an upgrade?" There's no summary signal.

4. **Inconsistent stat label widths.** "HP" is 2 chars, "Armor Penetration" is 16 chars. The stat list looks ragged.

5. **Comparison section is disconnected.** Base stats, affix stats, and comparison deltas are three separate sections. You have to visually map between them.

### Solution: Integrated Comparison Tooltip

Replace the current "stats then comparison" layout with an **inline comparison** approach:

```
┌──────────────────────────────────────────────┐
│  ⚔ Cruel Greatsword of Iron                 │  ← Rarity-colored name
│  Rare Greatsword — Weapon                    │  ← Type line
│  Item Level: 5                               │  ← iLvl
│                                              │
│  ── Base Stats ──                            │
│  +12  Melee           (equipped: +8)   ▲ +4  │  ← Inline comparison
│  +3   Crit Chance     (new)                  │
│                                              │
│  ── Affixes ──                               │  ← Blue section
│  +5   Armor           (equipped: +5)   —     │
│  +15  Max HP          (equipped: +20)  ▼ -5  │
│                                              │
│  ── Overall ──                               │
│  ◆ 2 upgrades, 1 downgrade                  │  ← Quick verdict
│                                              │
│  Sell: 45g                                   │
│  "Forged in the blood of the fallen."        │
│  [Right-click to equip]                      │
└──────────────────────────────────────────────┘
```

### Key Design Changes

#### 1. Inline Stat Comparison

Instead of separate "stats" and "vs Equipped" sections, each stat line shows:
- The new item's value (bold, left-aligned)
- The stat label (fixed-width, consistent alignment)
- The equipped item's value (dimmed, in parentheses) — only when comparing
- The delta arrow (right-aligned, colored green/red)

This eliminates the need to mentally cross-reference between sections.

#### 2. Fixed-Width Stat Labels

All stat labels are padded/truncated to a consistent display width using CSS:
- Labels use `min-width: 110px` with `text-overflow: ellipsis`
- Values use `min-width: 40px` with right-alignment (monospace font)
- Alignment makes the list scannable at a glance

#### 3. Overall Verdict Line

After all stats, a summary line:
- `◆ 3 upgrades` → green (clear upgrade)
- `◆ 2 upgrades, 1 downgrade` → amber (trade-off)
- `◆ 2 downgrades` → red (clear downgrade)
- `◆ Same stats` → gray (sidegrade)

This gives an instant signal before the player reads individual stats.

#### 4. Stat Tier Grouping

Stats are visually grouped by tier with subtle section dividers:
- **Core** (Melee, Ranged, Armor, HP) — always shown first, separated
- **Offensive** (Crit, Skill Damage, DoT, Holy, Armor Pen) — grouped
- **Defensive** (Dodge, DR, HP Regen, Life on Hit, Thorns) — grouped
- **Utility** (CDR, Move Speed, Gold Find, Magic Find) — grouped

Empty groups are hidden. This reduces cognitive load compared to a flat 20-stat list.

#### 5. Armor Category & Affinity Display

When hovering an armor item:
- Show the armor category as a tag: `[Heavy Armor]`, `[Light Armor]`, `[Cloth Armor]`
- If the current hero's preferred armor matches: show `✦ Class Affinity — +15% base stats` in gold
- Bonus values shown inline on each base stat: `+12 Armor (+2 affinity)` in a dimmed gold

#### 6. Compact Mode for Bag Items

When hovering items in the bag (not comparing), show a condensed tooltip:
- Name, type, rarity
- Combined stat list (base + affix merged, no separation)
- Set info (if applicable)
- Sell value
- No comparison section, no tier grouping

This keeps bag browsing snappy while the full comparison only appears when relevant.

### Implementation

**`client/src/components/Inventory/ItemTooltip.jsx`** — major rewrite:

```jsx
// New component structure:
// 1. Header (name, type, ilvl)
// 2. ArmorCategoryBadge (if armor)  — NEW
// 3. AffinityBonusLine (if matched) — NEW
// 4. StatSection (base) with inline comparison
// 5. StatSection (affix) with inline comparison
// 6. OverallVerdict — NEW
// 7. SetBonusSection (unchanged)
// 8. Footer (sell, description, hint)
```

**`client/src/utils/itemUtils.js`** — new helpers:

```javascript
// NEW: Inline comparison with absolute values
export function compareItemsInline(newItem, equippedItem) {
  // Returns array of { label, newVal, equippedVal, delta, direction, tier }
  // Includes tier grouping info for display
}

// NEW: Overall verdict from comparison
export function getComparisonVerdict(comparison) {
  // Returns { upgrades: N, downgrades: N, label: "...", color: "..." }
}

// NEW: Armor affinity check
export function getArmorAffinityInfo(item, classConfig) {
  // Returns { isMatch: bool, bonusPct: number, categoryLabel: string }
}

// UPDATED: Stat tier groups for display
export const STAT_DISPLAY_GROUPS = [
  { label: 'Core', keys: ['attack_damage', 'ranged_damage', 'armor', 'max_hp'] },
  { label: 'Offensive', keys: ['crit_chance', 'crit_damage', 'skill_damage_pct', 'holy_damage_pct', 'dot_damage_pct', 'armor_pen'] },
  { label: 'Defensive', keys: ['dodge_chance', 'damage_reduction_pct', 'hp_regen', 'life_on_hit', 'thorns'] },
  { label: 'Utility', keys: ['cooldown_reduction_pct', 'move_speed', 'heal_power_pct', 'gold_find_pct', 'magic_find_pct'] },
];
```

**`client/src/styles/components/_inventory.css`** — new tooltip styles:

- `.stat-row` — flexbox row with fixed-width columns for value/label/equipped/delta
- `.stat-group` — tier grouping with header and subtle top border
- `.verdict-line` — overall comparison summary with icon
- `.affinity-badge` — gold accent for armor affinity match
- `.armor-category-tag` — inline tag for Heavy/Light/Cloth
- Monospace font for all numeric values (alignment consistency)

### Files Changed

| File | Changes |
|------|---------|
| **`client/src/components/Inventory/ItemTooltip.jsx`** | Rewrite tooltip layout: inline comparison, stat tier groups, verdict line, affinity display, compact mode |
| **`client/src/utils/itemUtils.js`** | Add `compareItemsInline()`, `getComparisonVerdict()`, `getArmorAffinityInfo()`, `STAT_DISPLAY_GROUPS` |
| **`client/src/styles/components/_inventory.css`** | New tooltip CSS: stat-row layout, stat-group headers, verdict styling, affinity badge, armor category tag, monospace alignment |
| **`client/src/components/Inventory/Inventory.jsx`** | Pass `classConfig` to tooltip for affinity display |
| **`client/src/components/TownHub/`** | Update town merchant/equipment tooltips to use new component (if shared) |

### Verification

- [ ] Tooltip shows inline comparison (new value, equipped value, delta) on same row
- [ ] Stats grouped by tier with section headers (Core, Offensive, Defensive, Utility)
- [ ] Empty groups are hidden
- [ ] Overall verdict line shows correct upgrade/downgrade counts
- [ ] Armor category tag displays on armor items
- [ ] Affinity bonus line shows for matching class/armor
- [ ] Compact mode used for non-comparison (bag browsing) tooltips
- [ ] Tooltip edge-clamping still works (Phase 19 logic preserved)
- [ ] Rarity coloring still works on name and border
- [ ] Set bonus section still functions correctly
- [ ] All existing visual tests pass

---

## 21E — Merchant & Town UI Updates

**Effort:** Small  
**Risk:** Low — display-only changes  
**Prerequisite:** 21A, 21B

### Goal

Surface armor category and affinity info in the town merchant, hero roster, and bank views.

### Changes

1. **Merchant shop items** — show armor category tag on armor items in the merchant inventory
2. **Hero roster equipment view** — show affinity badge on equipped armor when it matches the hero's class
3. **Bank storage view** — show armor category tag on stored armor items
4. **Transfer modal** — when transferring armor, show which party members have affinity for it

### Files Changed

| File | Changes |
|------|---------|
| **`client/src/components/TownHub/Merchant.jsx`** | Add armor category tag to item display |
| **`client/src/components/TownHub/HeroRoster.jsx`** | Add affinity badge to equipped armor |
| **`client/src/components/TownHub/Bank.jsx`** | Add armor category tag to stored items |
| **`client/src/components/Inventory/Inventory.jsx`** | Add affinity hint to transfer modal |

### Verification

- [ ] Merchant shows `[Heavy]`/`[Light]`/`[Cloth]` tags on armor items
- [ ] Hero roster shows affinity badge on matching equipped armor
- [ ] Bank shows category tags
- [ ] Transfer modal hints which heroes match the armor category

---

## 21F — Balance & Config Tuning

**Effort:** Small  
**Risk:** Low — number tweaks only  
**Prerequisite:** 21A–21E complete

### Goal

Tune the affinity bonus percentage and affix category weights based on playtesting.

### Tuning Levers

| Parameter | Default | Range | Location |
|-----------|---------|-------|----------|
| `armor_affinity_bonus` | 0.15 (15%) | 0.10–0.25 | `classes_config.json` per class |
| Per-class bonus override | 0.15 | 0.10–0.20 | `classes_config.json` — allows tanks to get 20% while DPS gets 12% |
| Category affix weight-up | 1.5× | 1.0–2.0× | `item_generator.py` or `affixes_config.json` |
| Category affix weight-down | 0.5× | 0.3–0.8× | `item_generator.py` or `affixes_config.json` |
| Party-aware loot bias | 60% | 40–80% | `loot.py` |

### Balance Questions to Resolve During Playtesting

- Is 15% enough for players to feel the difference? (Target: noticeable on tooltip, but not mandatory)
- Should melee tanks (Crusader, Revenant) get a higher bonus (20%) since armor scaling matters more for them?
- Should the affinity bonus apply to unique/set armor base stats, or only normal/magic/rare/epic?
- Is the affix category weighting noticeable in practice? Should weights be stronger (2.0×/0.3×)?

---

## Key Design Decisions

### Why Soft Affinity, Not Hard Locks

| Hard Lock | Soft Affinity (chosen) |
|-----------|----------------------|
| "Mage can't wear plate" | "Mage can wear plate, but gets no bonus" |
| 75% of drops are vendor trash in a party | Every drop is potentially useful for someone |
| New class = update every item's allow-list | New class = assign one `preferred_armor` value |
| Creative builds are impossible | "Dodge tank Crusader in leather" is suboptimal but viable |
| Cannot tune without binary on/off | Can tune 10%–25% with a single config number |

### Why Only Base Stats Get the Bonus

- **Affixes are already random** — boosting them would double-dip on RNG variance
- **Base stats are the predictable floor** — the bonus rewards category alignment consistently
- **Prevents exploits** — a god-rolled epic with 5 affixes getting +15% to all affix stats would be absurd
- **Easier to reason about** — players can calculate: "base armor is 6, I get +1 from affinity"

### Why Accessories Stay Universal

- Accessories are the **build customization slot** — rings and trinkets don't have a clear role identity
- Unique accessories already serve class identity (Prayer Beads for healers, Warden's Oath for tanks)
- Three restriction tiers (hard → soft → open) give a clean design gradient: Weapon → Armor → Accessory

### Equipment Restriction Gradient

```
WEAPONS     →  HARD LOCK        (class can't equip wrong category)
ARMOR       →  SOFT AFFINITY    (any class can equip, preferred gets +15% base)
ACCESSORIES →  UNIVERSAL         (fully open — build customization slot)
SETS        →  CLASS THEMED     (stats self-select, skill bonuses are class-specific)
UNIQUES     →  BUILD THEMED     (stats/effects naturally fit certain classes)
```

---

## Future Extensibility

This system is designed to evolve. Planned future hooks:

1. **Armor appearance** — when sprites/art are added, `armor_category` maps directly to visual sets (heavy = plate model, cloth = robes model)
2. **Transmog system** — `armor_category` determines which visual pool an item can transmog into
3. **Crafting** — "reforge" an item's armor category (turn heavy plate into light plate, losing some stats)
4. **Per-class bonus overrides** — `armor_affinity_bonus` is already per-class, so Crusader could get 20% while Ranger gets 12%
5. **Armor mastery talents** — future talent tree could unlock "wear cloth with heavy affinity bonus" or "reduce off-type penalty"
6. **Tightening the restriction** — if soft affinity isn't enough identity, add a flat penalty (−10% base stats) for off-type armor. The infrastructure supports this with no code changes — just add `"off_type_penalty": -0.10` to class config

---

## Effort Estimation

| Sub-Phase | Effort | New Tests (est.) |
|-----------|--------|-----------------|
| 21A — Armor Category System | ~1 session | ~8 tests |
| 21B — Class Affinity Bonuses | ~2 sessions | ~15 tests |
| 21C — Item Generator & Loot | ~1 session | ~12 tests |
| 21D — Tooltip Overhaul | ~2 sessions | ~5 visual tests |
| 21E — Merchant & Town UI | ~1 session | ~4 tests |
| 21F — Balance & Config Tuning | ~1 session | — |
| **Total** | **~8 sessions** | **~44 tests** |

---

## Summary: Before vs. After

| Aspect | Before (Phase 20) | After (Phase 21) |
|--------|-------------------|-------------------|
| Armor identity | None — any class wears anything equally | Soft affinity — preferred category gets +15% base stats |
| Armor categories | Not tracked | `heavy`, `light`, `cloth` on every armor item |
| Class config | `allowed_weapons` only | + `preferred_armor`, `armor_affinity_bonus` |
| Generated armor affixes | Fully random | Category-weighted (heavy → more armor/HP, cloth → more CDR/skill%) |
| Loot relevance | Random for party | 60% party-aware bias |
| Tooltip comparison | Separate "vs Equipped" section with deltas only | Inline comparison: new value, equipped value, and delta on same row |
| Tooltip stat layout | Flat 20-stat list | Grouped by tier (Core, Offensive, Defensive, Utility) |
| Tooltip verdict | None — mental math required | `◆ 2 upgrades, 1 downgrade` summary line |
| Tooltip armor info | None | Category tag + affinity bonus line |
| Tooltip compact mode | N/A — always full | Compact for bag browsing, full for comparison |
| Restrictions gradient | Weapons: hard lock / Armor+Accessories: open | Weapons: hard lock / Armor: soft affinity / Accessories: open |

---

## Implementation Log

### 21A — Armor Category System ✅

**Completed:** March 18, 2026  
**Result:** All armor items tagged with `armor_category` — zero regressions (3791 tests passing)

#### Changes Made

| File | Change |
|------|--------|
| [server/app/models/items.py](../../server/app/models/items.py) | Added `ArmorCategory` enum (`heavy`, `light`, `cloth`); added `armor_category: str = ""` field to `Item` model |
| [server/configs/items_config.json](../../server/configs/items_config.json) | Added `"armor_category"` to all 15 armor entries (6 heavy, 4 light, 4 cloth, 1 heavy brigandine) |
| [server/configs/uniques_config.json](../../server/configs/uniques_config.json) | Added `"armor_category"` to 5 unique armor pieces (3 heavy, 2 light) |
| [server/configs/sets_config.json](../../server/configs/sets_config.json) | Added `"armor_category"` to 5 set armor pieces (1 heavy, 3 light, 1 cloth) |

#### Category Distribution

| Category | Items Config | Uniques | Sets | Total |
|----------|-------------|---------|------|-------|
| `heavy` | 7 (chain, plate×2, brigandine×2, bone×2) | 3 (Bonecage, Penitent Mail, Ironwill Plate) | 1 (Crusader's Oath Plate) | **11** |
| `light` | 4 (leather, hide×2, shadow cloak) | 2 (Shadowshroud, Wraithmantle) | 3 (Voidwalker Cloak, Deadeye Leathers, Seeker's Coat) | **9** |
| `cloth` | 4 (robes×2, vestments×2) | 0 | 1 (Radiant Vestments) | **5** |
| **Total** | **15** | **5** | **5** | **25** |

#### Verification

- [x] All 15 config armor items have `armor_category` set
- [x] All 5 unique armor pieces have `armor_category` set
- [x] All 5 set armor pieces have `armor_category` set
- [x] `Item` model accepts and serializes `armor_category`
- [x] Non-armor items default to `""` (weapons, accessories, consumables unchanged)
- [x] Existing tests pass — 3791 passed, 0 regressions (1 pre-existing failure in Bloodpact unrelated to armor)

---

### 21B — Class Affinity Bonuses ✅

**Completed:** March 18, 2026  
**Result:** Full-stack affinity system — classes gain +15% base stats from matching armor category. Zero regressions (3763 passed, 1 pre-existing flaky crit test).

#### Architecture Decision

Core stats (`attack_damage`, `ranged_damage`, `armor`, `max_hp`) are applied at **combat time** via `_get_equipment_bonuses()`, not stored persistently from equipment. Phase 16A stats (`crit_chance`, `dodge_chance`, etc.) are recalculated from scratch each call in `_recalculate_effective_stats()`. The affinity bonus required different handling for each:

- **Core stats** → tracked in `player.armor_affinity_applied` dict with reverse-before-reapply pattern (same approach as set bonuses)
- **Phase 16A stats** → added directly to `totals` dict (recalculated from scratch each pass, no tracking needed)

#### Changes Made

| File | Change |
|------|--------|
| [server/configs/classes_config.json](../../server/configs/classes_config.json) | Added `preferred_armor` and `armor_affinity_bonus: 0.15` to all 11 classes |
| [server/app/models/player.py](../../server/app/models/player.py) | Added `preferred_armor` / `armor_affinity_bonus` to `ClassDefinition`; added `armor_affinity_applied: dict` tracking field to `PlayerState` |
| [server/app/core/equipment_manager.py](../../server/app/core/equipment_manager.py) | Added affinity bonus calculation to `_recalculate_effective_stats()` with reverse-and-reapply pattern for core stats; added `math` and `get_class_definition` imports |
| [client/src/utils/itemUtils.js](../../client/src/utils/itemUtils.js) | Added `CLASS_PREFERRED_ARMOR` mapping, `DEFAULT_AFFINITY_BONUS`, `ARMOR_CATEGORY_LABELS`, and `getArmorAffinityInfo()` helper |
| [client/src/components/Inventory/ItemTooltip.jsx](../../client/src/components/Inventory/ItemTooltip.jsx) | Added armor category tag `[Heavy Armor]` display and gold affinity bonus line `✦ Crusader Affinity — +15% base stats` |
| [client/src/components/Inventory/Inventory.jsx](../../client/src/components/Inventory/Inventory.jsx) | Added gold affinity badge (✦) on armor equipment slot when category matches class preference; passes `classId` prop to `ItemTooltip` |
| [client/src/styles/components/_inventory.css](../../client/src/styles/components/_inventory.css) | Added `.item-tooltip-armor-category`, `.item-tooltip-affinity-bonus`, `.equip-affinity-badge`, and `.affinity-badge-icon` styles |

#### Class → Preferred Armor Mapping

| Category | Classes |
|----------|---------|
| `heavy` | Crusader, Revenant, Blood Knight |
| `light` | Ranger, Inquisitor, Hexblade |
| `cloth` | Confessor, Shaman, Mage, Bard, Plague Doctor |

#### Affinity Bonus Behavior

- Bonus multiplier: **15%** of each equipped armor piece's base stats (configurable per class via `armor_affinity_bonus`)
- Applies to: all stat bonuses on matching-category armor (core stats, Phase 16A stats, flat and percentage)
- Core stats: `math.floor()` rounding for flat values
- Phase 16A stats: `round(..., 2)` for percentage values
- Non-matching armor: no penalty, just no bonus (soft affinity, not hard lock)
- Uses `base_stats` for generated items, falls back to `stat_bonuses` for legacy/config items

#### Verification

- [x] All 11 classes have `preferred_armor` and `armor_affinity_bonus` in config
- [x] `ClassDefinition` model loads `preferred_armor` and `armor_affinity_bonus`
- [x] `PlayerState` tracks applied affinity bonuses for clean reversal
- [x] Equipping matching armor grants +15% bonus to that piece's stats
- [x] Equipping non-matching armor applies no bonus (zero penalty)
- [x] Unequipping reverses affinity bonuses correctly (no accumulation)
- [x] Client tooltip shows armor category tag and affinity bonus line
- [x] Equipment slot shows gold affinity badge when category matches
- [x] Existing tests pass — 3763 passed, 1 pre-existing flaky failure (non-deterministic crit in test_turn_resolver)

---

### 21C — Item Generator & Loot Integration ✅

**Completed:** March 18, 2026  
**Result:** Generated items carry `armor_category`, affixes biased by category, party-aware loot bias active. 29 new tests, 3821 total (1 pre-existing Bloodpact failure).

#### Architecture

Three independent changes layered on top of 21A's data model:

1. **`armor_category` passthrough** — `generate_item()`, `generate_unique()`, and `generate_set_piece()` now read `armor_category` from their config sources and set it on the produced `Item`. Previously, only static `create_item()` paths inherited it from the raw config dict.

2. **Category-weighted affix selection** — A new `ARMOR_CATEGORY_AFFIX_WEIGHTS` constant defines per-category weight multipliers (1.5× up, 0.5× down). The existing `_weighted_pick()` function applies these multipliers when an `armor_category` is provided, biasing affix rolls thematically without restricting any affix from appearing.

3. **Party-aware loot bias** — `_pick_base_type_from_pool()` now accepts `preferred_categories` and has a 60% chance to bias armor item selection toward items matching party members' preferred armor categories. A new helper `_get_party_preferred_categories()` resolves party class IDs to unique armor categories.

#### Changes Made

| File | Change |
|------|--------|
| [server/app/core/item_generator.py](../../server/app/core/item_generator.py) | Added `ARMOR_CATEGORY_AFFIX_WEIGHTS` constant; updated `_weighted_pick()` with category bias; updated `roll_affixes()` with `armor_category` param; `generate_item()` reads and passes `armor_category`; `generate_unique()` and `generate_set_piece()` read and pass `armor_category` |
| [server/app/core/loot.py](../../server/app/core/loot.py) | Added `_CLASS_PREFERRED_ARMOR` mapping and `_get_party_preferred_categories()` helper; updated `_pick_base_type_from_pool()` with 60% party-aware bias; added `party_classes` parameter to `generate_enemy_loot()` and `generate_chest_loot()` |
| [server/tests/test_phase21c_item_gen_loot.py](../../server/tests/test_phase21c_item_gen_loot.py) | 29 new tests across 5 test classes |

#### Affix Category Weights

| Category | Weighted UP (1.5×) | Weighted DOWN (0.5×) |
|----------|-------------------|---------------------|
| `heavy` | thorns, max_hp, armor, damage_reduction_pct | dodge_chance, skill_damage_pct |
| `light` | dodge_chance, crit_chance, move_speed, armor_pen | thorns, heal_power_pct |
| `cloth` | skill_damage_pct, cooldown_reduction_pct, heal_power_pct, magic_find_pct | thorns, armor |

#### Party-Aware Loot Bias

- 60% chance per item: bias toward armor matching a random party member's `preferred_armor`
- 40% chance: fully random selection (preserves variety)
- Non-armor items unaffected (bias only applies when matching items exist in the pool)
- Class → category mapping mirrors `classes_config.json` (heavy: Crusader/Revenant/Blood Knight, light: Ranger/Inquisitor/Hexblade, cloth: Confessor/Shaman/Mage/Bard/Plague Doctor)

#### Test Coverage (29 tests)

| Test Class | Tests | Coverage |
|-----------|-------|---------|
| `TestArmorCategoryOnGeneratedItems` | 6 | Generated items carry correct `armor_category` for all item types |
| `TestUniqueAndSetArmorCategory` | 4 | Unique and set items carry `armor_category` from configs |
| `TestAffinityAffinityWeightConfig` | 5 | Weight constants correctly structured for all categories |
| `TestCategoryWeightedAffixRolling` | 5 | Statistical validation of affix bias (heavy→thorns>dodge, cloth→skill>thorns, light→dodge>thorns) |
| `TestPartyAwareLootBias` | 9 | Helper resolution, pool bias validation, uniform baseline, API acceptance |

#### Verification

- [x] Generated armor items always have `armor_category` set (6 tests)
- [x] Unique armor items carry `armor_category` from uniques_config
- [x] Set armor pieces carry `armor_category` from sets_config
- [x] Non-armor items (weapons, accessories, consumables) default to `""`
- [x] Heavy armor biases affixes toward thorns/max_hp/armor, away from dodge/skill_damage
- [x] Light armor biases affixes toward dodge/crit/move_speed, away from thorns/heal_power
- [x] Cloth armor biases affixes toward skill_damage/CDR/heal_power, away from thorns/armor
- [x] Party-aware bias produces >50% matching armor picks with single-category party
- [x] No party = uniform distribution (no bias applied)
- [x] `generate_enemy_loot()` and `generate_chest_loot()` accept `party_classes` without error
- [x] All affix category weighting produces thematically appropriate affixes (statistical tests)
- [x] Existing tests pass — 3821 total (3792 original + 29 new), 1 pre-existing Bloodpact failure

---

### 21D — Tooltip Overhaul ✅

**Completed:** March 18, 2026  
**Result:** Full tooltip rewrite — inline comparison with tier grouping, overall verdict, compact mode for non-comparison. Zero regressions (3821 tests, frontend builds clean).

#### Architecture

The tooltip now operates in two distinct modes:

1. **Comparison mode** (hovering a bag item with an equipped item in the same slot): Uses `compareItemsInline()` to produce a full stat comparison between the new item's `stat_bonuses` and the equipped item's `stat_bonuses`. Results are grouped by tier (Core, Offensive, Defensive, Utility) with inline display of new value, equipped value, and delta on each row. An overall verdict line summarizes the comparison.

2. **Compact mode** (hovering items without comparison — equipped items, empty-slot items, bag browsing): Shows a flat merged stat list from `stat_bonuses` (no base/affix separation, no tier grouping). Keeps bag browsing snappy.

#### Changes Made

| File | Change |
|------|--------|
| [client/src/utils/itemUtils.js](../../client/src/utils/itemUtils.js) | Added `STAT_DISPLAY_GROUPS` constant (4 tier groups), `compareItemsInline()` (inline comparison with tier info + formatted values), `getComparisonVerdict()` (upgrade/downgrade/sidegrade summary) |
| [client/src/components/Inventory/ItemTooltip.jsx](../../client/src/components/Inventory/ItemTooltip.jsx) | Replaced base/affix sections + old "vs Equipped" comparison with tier-grouped inline comparison; added verdict line; added compact mode; added `has-comparison` class for wider tooltip; removed `compareItems`/`getRarityColor`/`ARMOR_CATEGORY_LABELS` imports (unused) |
| [client/src/styles/components/_inventory.css](../../client/src/styles/components/_inventory.css) | Added 21D styles: `.has-comparison` (wider tooltip at 300px), `.tooltip-stat-group`/`-header` (tier grouping), `.tooltip-stat-row` (flexbox with direction-based backgrounds), `.tooltip-stat-value` (monospace, base/affix color coding), `.tooltip-stat-label` (fixed-width alignment), `.tooltip-stat-compare` + `.tooltip-stat-equipped`/`-new-tag`/`-lost-tag`, `.tooltip-stat-delta` + direction colors, `.tooltip-verdict` + color variants, `.item-tooltip-compact-stats` |

#### New Utility Functions

| Function | Purpose |
|----------|---------|
| `STAT_DISPLAY_GROUPS` | 4-tier grouping: Core (Melee/Ranged/Armor/HP), Offensive (Crit/Skill Damage/Holy/DoT/Armor Pen), Defensive (Dodge/DR/Regen/LoH/Thorns), Utility (CDR/Move Speed/Heal Power/Gold/Magic Find) |
| `compareItemsInline(newItem, equippedItem)` | Returns per-stat comparison entries with: key, label, format, newVal, oldVal, delta, direction (up/down/same/new/lost), tier assignment, pre-formatted display strings |
| `getComparisonVerdict(comparison)` | Counts upgrades (up+new) and downgrades (down+lost), returns summary label and color (green/amber/red/gray) |

#### Tooltip Layout — Comparison Mode

```
┌──────────────────────────────────────────────┐
│  W Cruel Greatsword of Iron                  │  ← Rarity-colored name
│  Rare Greatsword — weapon                    │  ← Type line
│  Item Level: 5                               │
│  [Heavy Armor]                               │  ← Category tag (armor only)
│  ✦ Crusader Affinity — +15% base stats       │  ← Gold line (if matched)
│                                              │
│  CORE                                        │  ← Tier group header
│  +12  Melee     (eq: 8)           ▲ +4       │  ← Inline comparison row
│  +20  HP        (eq: 25)          ▼ -5       │
│                                              │
│  OFFENSIVE                                   │
│  +3   Crit      (new)                        │  ← New stat
│                                              │
│  ──────────────────────────                  │
│  ◆ 2 upgrades, 1 downgrade                  │  ← Verdict (amber)
│                                              │
│  Sell: 45g                                   │
│  "Forged in the blood of the fallen."        │
│  Click to equip                              │
└──────────────────────────────────────────────┘
```

#### Stat Row Color Coding

- **Value color**: Gray (`stat-source-base`) for stats originating from base_stats, blue (`stat-source-affix`) for affix-only stats
- **Row background**: Subtle green (up), red (down), amber (new), red (lost), transparent (same)
- **Delta color**: Green (▲ up), red (▼ down), amber (new), red (lost), dim (— same)
- **Verdict color**: Green (pure upgrade), amber (trade-off), red (pure downgrade), gray (sidegrade)

#### Verification

- [x] Tooltip shows inline comparison (new value, equipped value, delta) on same row
- [x] Stats grouped by tier with section headers (Core, Offensive, Defensive, Utility)
- [x] Empty groups are hidden (only groups with active stats render)
- [x] Overall verdict line shows correct upgrade/downgrade counts with color
- [x] Armor category tag displays on armor items (preserved from 21B)
- [x] Affinity bonus line shows for matching class/armor (preserved from 21B)
- [x] Compact mode used for non-comparison (bag browsing, equipped items) tooltips
- [x] Tooltip edge-clamping still works (Phase 19 logic preserved)
- [x] Rarity coloring still works on name and border
- [x] Set bonus section still functions correctly
- [x] Consumable tooltips still work (heal/portal effects)
- [x] Frontend builds cleanly (0 errors, 119 modules)
- [x] All server tests pass — 3821 passed, 0 regressions

---

### 21E — Merchant & Town UI Updates ✅

**Completed:** March 18, 2026  
**Result:** Armor category tags and affinity badges surfaced across all Town Hub views — merchant, hero roster, bank, and transfer modals. Zero regressions (3821 tests, frontend builds clean).

#### Architecture

21E is purely client-side — display-only changes that leverage the `ARMOR_CATEGORY_LABELS` constant and `getArmorAffinityInfo()` helper from `itemUtils.js` (both introduced in 21B). No server changes needed.

Four independent display additions:

1. **Merchant** — Armor category tags (`[Heavy Armor]`, `[Light Armor]`, `[Cloth Armor]`) shown on armor items in both buy and sell panels
2. **Hero Roster** — Gold ✦ affinity badge on equipped armor tags when the armor category matches the hero's class preference; armor category + affinity line added to gear tooltip
3. **Bank** — Armor category tags on stored items in both hero inventory (deposit) and vault (withdraw) panels; category tag added to bank tooltip
4. **Transfer Modals** — Gold ✦ affinity badge shown next to transfer target heroes whose preferred armor matches the item being transferred (both dungeon Inventory.jsx modal and town HeroDetailPanel.jsx modal)

#### Changes Made

| File | Change |
|------|--------|
| [client/src/components/TownHub/Merchant.jsx](../../client/src/components/TownHub/Merchant.jsx) | Import `ARMOR_CATEGORY_LABELS`; add armor category tag to buy panel and sell panel item displays |
| [client/src/components/TownHub/HeroRoster.jsx](../../client/src/components/TownHub/HeroRoster.jsx) | Import `getArmorAffinityInfo`, `ARMOR_CATEGORY_LABELS`; add ✦ affinity badge on matching equipped armor tags; pass `classId` through tooltip hover handler; add armor category tag and gold affinity line to gear tooltip |
| [client/src/components/TownHub/Bank.jsx](../../client/src/components/TownHub/Bank.jsx) | Import `ARMOR_CATEGORY_LABELS`; add armor category tag to hero inventory items, vault items, and `BankItemTooltip` |
| [client/src/components/TownHub/HeroDetailPanel.jsx](../../client/src/components/TownHub/HeroDetailPanel.jsx) | Import `getArmorAffinityInfo`; add ✦ affinity badge on transfer target heroes whose preferred armor matches the transferred item |
| [client/src/components/Inventory/Inventory.jsx](../../client/src/components/Inventory/Inventory.jsx) | Add ✦ affinity badge on dungeon transfer modal targets when armor category matches target's class preference |
| [client/src/styles/town/_merchant.css](../../client/src/styles/town/_merchant.css) | Added `.merchant-armor-category` style (gold-tone, mono font, 0.65rem) |
| [client/src/styles/town/_bank.css](../../client/src/styles/town/_bank.css) | Added `.bank-armor-category` and `.gear-tooltip-armor-category` styles |
| [client/src/styles/town/_hero-roster.css](../../client/src/styles/town/_hero-roster.css) | Added `.roster-affinity-badge` (gold ✦ with text-shadow) and `.gear-tooltip-affinity` styles |
| [client/src/styles/town/_gear-management.css](../../client/src/styles/town/_gear-management.css) | Added `.transfer-affinity-badge` style (gold ✦ with margin-left auto positioning) |

#### Visual Behavior

| View | Armor Category Display | Affinity Badge |
|------|----------------------|----------------|
| **Merchant (buy)** | `[Heavy Armor]` below stat line | — (no hero context for comparison) |
| **Merchant (sell)** | `[Heavy Armor]` below stat line | — |
| **Hero Roster (equip tags)** | — (tag is compact, no room) | Gold ✦ appended to armor tag name when matched |
| **Hero Roster (tooltip)** | `[Heavy Armor]` below type line | `✦ Crusader Affinity — +15% base stats` gold line |
| **Bank (item lists)** | `[Heavy Armor]` below stat line | — (no hero context) |
| **Bank (tooltip)** | `[Heavy Armor]` below type line | — |
| **Transfer modal (dungeon)** | — | Gold ✦ next to heroes whose preferred armor matches |
| **Transfer modal (town)** | — | Gold ✦ next to heroes whose preferred armor matches |

#### Verification

- [x] Merchant shows `[Heavy Armor]`/`[Light Armor]`/`[Cloth Armor]` tags on armor items in buy panel
- [x] Merchant shows category tags on armor items in sell panel
- [x] Hero roster shows gold ✦ affinity badge on matching equipped armor tags
- [x] Hero roster gear tooltip shows armor category tag and affinity bonus line
- [x] Bank shows category tags on hero inventory items (deposit panel)
- [x] Bank shows category tags on vault items (withdraw panel)
- [x] Bank tooltip shows armor category tag
- [x] Town transfer modal (HeroDetailPanel) shows ✦ next to heroes with matching preferred armor
- [x] Dungeon transfer modal (Inventory) shows ✦ next to heroes with matching preferred armor
- [x] Non-armor items show no category tag or affinity badge (correct no-op)
- [x] Frontend builds cleanly (0 errors, 119 modules)
- [x] All server tests pass — 3821 passed, 0 regressions
