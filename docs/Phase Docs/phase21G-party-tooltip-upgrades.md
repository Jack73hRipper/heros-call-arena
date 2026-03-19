# Phase 21G — Party-Aware Tooltip & Gear Fit System

**Created:** March 18, 2026  
**Status:** Design Complete — Ready for Implementation  
**Previous:** Phase 21E (Merchant & Town UI Updates)  
**Goal:** Solve the "is this gear useful for anyone?" problem by adding party-wide upgrade visibility to the item tooltip, bag display, and comparison flow.

---

## The Problem

Phase 21D's tooltip overhaul improved single-hero comparisons significantly — inline deltas, tier grouping, and a verdict line. But a fundamental UX gap remains:

**The tooltip only answers "is this better for the hero I'm currently looking at?"**

In a party of 4 heroes, you constantly pick up items that are downgrades for your active hero but upgrades for someone else. The current experience:

1. Pick up a Rare Mage Robe → tooltip shows `▼ 3 downgrades` (compared to Crusader's plate)
2. Player thinks "trash" and vendors it
3. Meanwhile, the Mage is still wearing Common Robes and would have gained +8 Skill Damage

The root issues:
- **No party context** — the tooltip doesn't show how the item compares for anyone except the viewed hero
- **Raw stats buried** — in comparison mode, the item's own stats are interleaved with deltas, making it hard to see what the item actually *is*
- **No passive signals** — you must hover every bag item and mentally recall every hero's gear to find upgrades
- **Switching heroes is tedious** — to compare for the Mage, you must click the Mage's party tab, find the item in the bag, and hover again

---

## Table of Contents

1. [Party Fit Roster on Tooltip](#21g-1--party-fit-roster-on-tooltip)
2. [Q-to-Cycle Comparison Target](#21g-2--q-to-cycle-comparison-target)
3. [Best-Fit Badge on Bag Items](#21g-3--best-fit-badge-on-bag-items)
4. [Implementation Notes](#implementation-notes)

---

## Phase Dependency Map

```
Phase 21D (Tooltip Overhaul — inline comparison, verdict, tier groups)
Phase 21B (Class Affinity Bonuses — getArmorAffinityInfo, CLASS_PREFERRED_ARMOR)
    │
    ├──► 21G-1 — Party Fit Roster (needs compareItemsInline + partyMembers)
    │       │
    │       └──► 21G-3 — Best-Fit Badge (reuses party comparison logic from 21G-1)
    │
    └──► 21G-2 — Q-to-Cycle (independent, needs partyMembers + keyboard handling)
```

---

## 21G-1 — Party Fit Roster on Tooltip

**Effort:** Medium  
**Risk:** Low — additive UI, no game logic changes  
**Prerequisite:** 21D (tooltip overhaul complete)

### Goal

Add a "Party Fit" section to the comparison tooltip that shows a one-line verdict for every party hero, instantly answering "who should get this item?"

### Design

When hovering a bag item that triggers comparison mode, the tooltip gains a new section below the verdict:

```
┌──────────────────────────────────────────────┐
│  ⚔ Cruel Mage Robes of Fire                 │
│  Rare Robes — armor                          │
│  [Cloth Armor]                               │
│                                              │
│  CORE                                        │
│  +2   Armor     (eq: 8)           ▼ -6       │
│  +10  HP        (eq: 25)          ▼ -15      │
│                                              │
│  OFFENSIVE                                   │
│  +8   Skill Dmg (new)                        │
│  +3   Crit      (eq: 2)           ▲ +1       │
│                                              │
│  ◆ 1 upgrade, 2 downgrades                  │
│                                              │
│  ── Party Fit ──────────────────────         │
│  Crusader   ▼ worse    (current)             │  ← Currently viewed hero
│  Mage       ▲ upgrade  ★ best fit            │  ← Gold star = best match
│  Ranger     — same                           │
│  Confessor  ▲ upgrade  ✦                     │  ← ✦ = armor affinity match
└──────────────────────────────────────────────┘
```

### Logic

For each party member:

1. Look up their equipped item in the same slot (`partyInventories[unitId].equipment[slot]`)
2. Call `compareItemsInline(hoveredItem, equippedItem)` to get stat deltas
3. Call `getComparisonVerdict(comparison)` to get upgrade/downgrade counts
4. Compute a simple **fit score**: `upgrades - downgrades` (higher = better fit)
5. Mark the hero with the highest fit score as `★ best fit`
6. If the item is armor, check `getArmorAffinityInfo(item, hero.class_id)` — if matched, append `✦`
7. If the hero has no item in that slot, show `▲ empty slot` (any item is an upgrade over nothing)

### Verdict Display per Hero

| Condition | Display | Color |
|-----------|---------|-------|
| fitScore > 0 | `▲ upgrade` | Green |
| fitScore === 0, changes exist | `↔ trade-off` | Amber |
| fitScore === 0, no changes | `— same` | Gray |
| fitScore < 0 | `▼ worse` | Red/dim |
| No equipped item in slot | `▲ empty slot` | Green |
| Is the currently viewed hero | append `(current)` | Dim |

### Best Fit Star Logic

- The hero with the highest `fitScore` gets `★ best fit` in gold
- Ties broken by: (a) armor affinity match, (b) total upgrade magnitude (sum of positive deltas), (c) first in party order
- If all heroes are downgrades, no star is shown (the item is genuinely bad for everyone)
- If the item isn't equippable by any hero (e.g., it's a consumable), the Party Fit section is hidden

### Data Flow

```
Inventory.jsx
  │
  ├── partyMembers[]          ← from useGameState()
  ├── partyInventories{}      ← from useGameState()  
  ├── players{}               ← from useGameState()
  │
  └──► <ItemTooltip
         item={hoveredItem}
         equippedItem={...}
         classId={unitClassId}
         partyMembers={partyMembers}          ← NEW prop
         partyInventories={partyInventories}  ← NEW prop
         players={players}                    ← NEW prop
       />

ItemTooltip.jsx
  │
  ├── For each partyMember:
  │     heroEquipped = partyInventories[member.unit_id]?.equipment[item.equip_slot]
  │     comparison = compareItemsInline(item, heroEquipped)
  │     verdict = getComparisonVerdict(comparison)
  │     fitScore = verdict.upgrades - verdict.downgrades
  │     affinity = getArmorAffinityInfo(item, member.class_id)
  │
  └── Render PartyFitRoster section
```

### New Utility Function

**`client/src/utils/itemUtils.js`** — add:

```javascript
/**
 * Compare an item against all party members' equipped gear in the same slot.
 * Returns an array of { unitId, className, classId, verdict, fitScore, 
 *                        isAffinityMatch, isBestFit, isCurrentHero } 
 */
export function getPartyFitRoster(item, partyMembers, partyInventories, players, currentUnitId) {
  if (!item?.equip_slot || !partyMembers?.length) return [];

  const slot = item.equip_slot;
  const results = partyMembers
    .filter(m => m.is_alive)
    .map(member => {
      const memberEquip = partyInventories[member.unit_id]?.equipment || {};
      const equippedItem = memberEquip[slot] || null;
      
      let verdict, fitScore;
      if (!equippedItem) {
        // Empty slot — any item is an upgrade
        verdict = { upgrades: 1, downgrades: 0, label: '▲ empty slot', color: 'green' };
        fitScore = 1;
      } else {
        const comparison = compareItemsInline(item, equippedItem);
        verdict = getComparisonVerdict(comparison);
        fitScore = verdict.upgrades - verdict.downgrades;
      }

      const affinity = getArmorAffinityInfo(item, member.class_id);

      return {
        unitId: member.unit_id,
        className: players[member.unit_id]?.class_id || member.class_id,
        displayName: member.username,
        verdict,
        fitScore,
        isAffinityMatch: affinity?.isMatch || false,
        isCurrentHero: member.unit_id === currentUnitId,
      };
    });

  // Determine best fit
  const bestScore = Math.max(...results.map(r => r.fitScore));
  if (bestScore > 0) {
    // Find the best candidate (tie-break: affinity match first, then first in party order)
    const bestCandidates = results.filter(r => r.fitScore === bestScore);
    const best = bestCandidates.find(r => r.isAffinityMatch) || bestCandidates[0];
    best.isBestFit = true;
  }

  return results;
}
```

### Files Changed

| File | Changes |
|------|---------|
| **`client/src/utils/itemUtils.js`** | Add `getPartyFitRoster()` function |
| **`client/src/components/Inventory/ItemTooltip.jsx`** | Add Party Fit section; accept new props (`partyMembers`, `partyInventories`, `players`) |
| **`client/src/components/Inventory/Inventory.jsx`** | Pass `partyMembers`, `partyInventories`, `players` to `ItemTooltip` |
| **`client/src/styles/components/_inventory.css`** | Add `.tooltip-party-fit`, `.party-fit-row`, `.party-fit-best`, `.party-fit-affinity` styles |

### CSS Additions

```css
/* ── Party Fit Section ── */
.tooltip-party-fit {
  margin-top: 0.3rem;
  padding-top: 0.25rem;
  border-top: 1px solid rgba(255, 255, 255, 0.08);
}

.tooltip-party-fit-header {
  font-size: 0.5rem;
  font-family: var(--font-heading);
  color: var(--text-dim);
  text-transform: uppercase;
  letter-spacing: 0.08em;
  margin-bottom: 0.15rem;
}

.party-fit-row {
  display: flex;
  align-items: center;
  gap: 0.3rem;
  font-size: 0.6rem;
  padding: 0.05rem 0.1rem;
  border-radius: 2px;
}

.party-fit-name {
  min-width: 65px;
  font-family: var(--font-heading);
  color: var(--text-secondary);
  font-size: 0.55rem;
  text-transform: capitalize;
}

.party-fit-verdict {
  flex: 1;
  font-family: var(--font-mono, monospace);
  font-size: 0.55rem;
}

.party-fit-verdict.fit-upgrade { color: #44cc44; }
.party-fit-verdict.fit-tradeoff { color: #ccaa00; }
.party-fit-verdict.fit-same { color: var(--text-dim); }
.party-fit-verdict.fit-worse { color: var(--text-dim); opacity: 0.6; }

.party-fit-badges {
  display: flex;
  gap: 0.15rem;
  flex-shrink: 0;
}

.party-fit-best {
  color: #e8c252;
  font-size: 0.6rem;
  font-weight: bold;
}

.party-fit-affinity {
  color: #e8c252;
  font-size: 0.55rem;
}

.party-fit-current {
  color: var(--text-dim);
  font-size: 0.5rem;
  font-style: italic;
}

/* Hide party fit when only one hero (solo mode) */
.tooltip-party-fit.single-hero { display: none; }
```

### Verification

- [x] Party Fit section appears on bag items that have an `equip_slot`
- [x] Each alive party member shown with correct verdict (upgrade/worse/same/trade-off)
- [x] Empty slot shows `▲ empty slot` in green
- [x] Best fit hero has `★` gold badge
- [x] Armor affinity match shows `✦` badge
- [x] Currently viewed hero labeled `(current)`
- [x] Party Fit hidden when only 1 hero (solo mode)
- [x] Party Fit hidden for consumables and non-equippable items
- [ ] Tooltip doesn't overflow viewport (edge-clamping still works with added height)
- [ ] No performance issues with 4-hero party (4 calls to `compareItemsInline` per hover)

### Implementation Log — 21G-1

**Completed:** March 18, 2026

**Files Changed:**
| File | Changes |
|------|---------|
| `client/src/utils/itemUtils.js` | Added `getPartyFitRoster()` — compares item against all party members' equipped gear, computes fit scores, determines best fit with affinity tie-breaking |
| `client/src/components/Inventory/ItemTooltip.jsx` | Added `partyMembers`, `partyInventories`, `players`, `currentUnitId` props; imports `getPartyFitRoster`; renders Party Fit section below verdict with per-hero verdict rows, best fit star, affinity badge, and (current) label |
| `client/src/components/Inventory/Inventory.jsx` | Added `allPartyInventories` memo that merges self player equipment into `partyInventories` for uniform lookups; passes `partyTabs`, `allPartyInventories`, `players`, `effectiveUnitId` to `ItemTooltip` |
| `client/src/styles/components/_inventory.css` | Added `.tooltip-party-fit`, `.tooltip-party-fit-header`, `.party-fit-row`, `.party-fit-name`, `.party-fit-verdict` (with `.fit-upgrade`/`.fit-tradeoff`/`.fit-same`/`.fit-worse`), `.party-fit-badges`, `.party-fit-best`, `.party-fit-affinity`, `.party-fit-current`, `.single-hero` hide rule |

**Key Implementation Details:**
- Self player's inventory/equipment is stored separately from `partyInventories` in game state, so `allPartyInventories` memo merges them into a unified lookup for `getPartyFitRoster`
- `partyTabs` (which includes self + all party members with `unit_id`, `username`, `class_id`, `is_alive`) is reused as the `partyMembers` prop to avoid duplicating the party list construction
- Verdict logic: fitScore > 0 = upgrade (green), fitScore < 0 = worse (dim), fitScore == 0 with mixed ups/downs = trade-off (amber), no changes = same (gray)

---

## 21G-2 — Q-to-Cycle Comparison Target

**Effort:** Small  
**Risk:** Low — keyboard handler + state change, no game logic  
**Prerequisite:** 21G-1 (party fit data available)

### Goal

While hovering a bag item, pressing **Q** cycles the tooltip's comparison target through party members, showing the full detailed comparison against each hero's gear without needing to switch party tabs.

> **Why Q?** Tab is already bound to "cycle enemy target" in combat (`useKeyboardShortcuts.js`), and Shift+Tab cycles in reverse. Q is free, sits on the left hand next to WASD, and is easy to tap while the right hand hovers with the mouse.

### Design

```
┌──────────────────────────────────────────────┐
│  ⚔ Cruel Mage Robes of Fire                 │
│  Rare Robes — armor                          │
│  [Cloth Armor]                               │
│                                              │
│  ┌─ Comparing for: Mage (2/4) ── [Q] ──┐   │  ← NEW header
│                                              │
│  ✦ Mage Affinity — +15% base stats          │  ← Affinity updates per hero
│                                              │
│  CORE                                        │
│  +2   Armor     (eq: 3)           ▼ -1       │  ← Now compared vs Mage's gear
│  +10  HP        (eq: 8)           ▲ +2       │
│                                              │
│  OFFENSIVE                                   │
│  +8   Skill Dmg (eq: 0)           ▲ +8       │
│                                              │
│  ◆ 2 upgrades, 1 downgrade                  │
│                                              │
│  ── Party Fit ──                             │
│  ...                                         │
└──────────────────────────────────────────────┘
```

### State Management

**`Inventory.jsx`** — new state:

```javascript
const [compareTargetIndex, setCompareTargetIndex] = useState(null);
// null = default (compare vs currently viewed hero)
// 0..N = index into alive partyMembers array
```

### Keyboard Handler

Add to the existing `useEffect` keydown handler in `Inventory.jsx`:

```javascript
if ((e.key === 'q' || e.key === 'Q') && hoveredItem && hoveredItem.source === 'bag') {
  e.preventDefault();
  const aliveMembers = partyMembers.filter(m => m.is_alive);
  if (aliveMembers.length <= 1) return; // No cycling with 1 hero
  
  setCompareTargetIndex(prev => {
    if (prev === null) return 0;
    return (prev + 1) % aliveMembers.length;
  });
}
```

### Comparison Target Resolution

```javascript
// Determine which hero's gear to compare against
const aliveMembers = partyMembers.filter(m => m.is_alive);
let compareUnitId = effectiveUnitId; // default: currently viewed hero
let compareClassId = unitClassId;

if (compareTargetIndex !== null && aliveMembers[compareTargetIndex]) {
  const target = aliveMembers[compareTargetIndex];
  compareUnitId = target.unit_id;
  compareClassId = target.class_id;
}

const compareEquipment = compareUnitId === effectiveUnitId
  ? viewEquipment
  : partyInventories[compareUnitId]?.equipment || {};
```

Update `ItemTooltip` prop:

```javascript
<ItemTooltip
  item={hoveredItem.item}
  equippedItem={
    hoveredItem.source === 'bag' && hoveredItem.item.equip_slot
      ? compareEquipment[hoveredItem.item.equip_slot] || null
      : null
  }
  classId={compareClassId}
  compareHeroName={aliveMembers[compareTargetIndex]?.username || null}
  compareHeroIndex={compareTargetIndex !== null ? compareTargetIndex + 1 : null}
  compareHeroTotal={aliveMembers.length}
  // ... existing props
/>
```

### Reset Behavior

- `compareTargetIndex` resets to `null` when:
  - `hoveredItem` changes (moved to a different bag slot)
  - Inventory closes
  - Party tab changes
- First Q press starts at index 0 (first alive member), not the currently viewed hero — this avoids a wasted keypress showing what you already see

### Tooltip Display

When `compareHeroName` is provided, show a header above the comparison:

```jsx
{compareHeroName && (
  <div className="tooltip-compare-target">
    Comparing for: <span className="compare-target-name">{compareHeroName}</span>
    <span className="compare-target-index">({compareHeroIndex}/{compareHeroTotal})</span>
    <span className="compare-target-hint">[Q]</span>
  </div>
)}
```

### Files Changed

| File | Changes |
|------|---------|
| **`client/src/components/Inventory/Inventory.jsx`** | Add `compareTargetIndex` state; add Q keydown handler; compute `compareEquipment`/`compareClassId`; pass new props to tooltip; reset on hover change |
| **`client/src/components/Inventory/ItemTooltip.jsx`** | Accept `compareHeroName`/`compareHeroIndex`/`compareHeroTotal` props; render comparison target header |
| **`client/src/styles/components/_inventory.css`** | Add `.tooltip-compare-target`, `.compare-target-name`, `.compare-target-hint` styles |

### CSS Additions

```css
/* ── Comparison Target Header ── */
.tooltip-compare-target {
  display: flex;
  align-items: center;
  gap: 0.25rem;
  font-size: 0.55rem;
  color: var(--text-dim);
  padding: 0.15rem 0.2rem;
  margin: 0.15rem 0;
  background: rgba(255, 255, 255, 0.03);
  border-radius: 2px;
  border: 1px solid rgba(255, 255, 255, 0.06);
}

.compare-target-name {
  color: var(--text-primary);
  font-family: var(--font-heading);
  text-transform: capitalize;
  font-weight: bold;
}

.compare-target-index {
  color: var(--text-dim);
  font-family: var(--font-mono, monospace);
  font-size: 0.5rem;
}

.compare-target-hint {
  margin-left: auto;
  color: var(--text-dim);
  opacity: 0.5;
  font-size: 0.5rem;
  font-family: var(--font-mono, monospace);
}
```

### Verification

- [x] Q key cycles comparison target through alive party members
- [x] Tooltip header shows "Comparing for: Mage (2/4) [Q]"
- [x] Stat comparison updates for the target hero's equipped gear
- [x] Affinity badge updates for the target hero's class
- [x] `compareTargetIndex` resets when hoveredItem changes
- [x] Q does not conflict with any existing keybinding
- [x] Q does nothing when hovering equipped items or only 1 hero exists
- [x] Party Fit section `(current)` label updates to reflect the comparison target
- [ ] No visual jank when cycling (tooltip repositions correctly)

### Implementation Log — 21G-2

**Completed:** March 18, 2026

**Files Changed:**
| File | Changes |
|------|---------|
| `client/src/components/Inventory/Inventory.jsx` | Added `compareTargetIndex` state; added Q keydown handler to existing `useEffect` (cycles through alive `partyTabs` members, guarded against non-bag items, single-hero, and input fields); reset `compareTargetIndex` to `null` in `handleSlotMouseEnter`, `handleSlotMouseLeave`, and `handlePartyTabClick`; computed `compareUnitId`/`compareClassId`/`compareEquipment` from `compareTargetIndex` + `aliveMembers` in the tooltip render block (IIFE); passes `compareHeroName`, `compareHeroIndex`, `compareHeroTotal` and updated `classId`/`currentUnitId`/`equippedItem` to `ItemTooltip` |
| `client/src/components/Inventory/ItemTooltip.jsx` | Added `compareHeroName`, `compareHeroIndex`, `compareHeroTotal` to destructured props; rendered "Comparing for: {name} ({index}/{total}) [Q]" header between affinity bonus and comparison groups when `compareHeroName` is set |
| `client/src/styles/components/_inventory.css` | Added `.tooltip-compare-target` (flex row, subtle background/border), `.compare-target-name` (bold, heading font, primary color), `.compare-target-index` (dim, mono), `.compare-target-hint` (auto-margin-left, faded [Q] label) |

**Key Implementation Details:**
- The tooltip render was converted from a plain JSX expression `{condition && <ItemTooltip .../>}` to an IIFE `{condition && (() => { ... })()}` to allow local variable computation for the comparison target resolution without adding more state or useMemo
- `compareEquipment` uses `allPartyInventories` (the merged inventory map from 21G-1) to look up any party member's equipment, falling back to `viewEquipment` for the currently viewed hero
- `currentUnitId` passed to tooltip updates to `compareUnitId` so the Party Fit roster's `(current)` label correctly tracks whichever hero the tooltip is currently comparing against
- `classId` updates to `compareClassId` so the armor affinity display in the tooltip reflects the cycled hero's class
- Q handler skips non-bag items (`hoveredItem.source !== 'bag'`) and items without an `equip_slot` (consumables) per spec

---

## 21G-3 — Best-Fit Badge on Bag Items

**Effort:** Small  
**Risk:** Low — visual overlay on bag slots, no interaction changes  
**Prerequisite:** 21G-1 (reuses `getPartyFitRoster` logic)

### Goal

Show a small colored indicator on each bag item that is an upgrade for at least one party hero, so players can spot upgrades at a glance without hovering.

### Design

Each bag slot that contains an equippable item gets a small badge in the top-right corner:

```
┌──────┐  ┌──────┐  ┌──────┐  ┌──────┐
│      │  │    ▲M│  │      │  │    ▲C│
│ Sword│  │Robes │  │Potion│  │Plate │
│      │  │      │  │      │  │      │
└──────┘  └──────┘  └──────┘  └──────┘
           Mage↑                Crusader↑
```

### Badge Rules

| Condition | Badge | Color | Meaning |
|-----------|-------|-------|---------|
| Best fit hero exists (fitScore > 0) | `▲` + first letter of class | Green | This is an upgrade for someone |
| Best fit is the currently viewed hero | `▲` + first letter | Bright green | Upgrade for you specifically |
| Multiple heroes could upgrade | `▲` + count (e.g. `▲2`) | Gold | Multiple heroes benefit |
| No upgrades for anyone | No badge | — | Not worth highlighting |
| Item is not equippable (consumable) | No badge | — | Consumables don't compare |

### Badge Details

- **Position:** Top-right corner of the bag slot, 12×12px circle
- **Background:** Semi-transparent dark with colored border
- **Text:** Single character — first letter of class name (C for Crusader, M for Mage, R for Ranger, etc.)
- **Fallback for ambiguity:** If two classes share first letter (no current case in 11 classes, but safe), use first 2 characters

### Class Abbreviation Map

```javascript
const CLASS_BADGE_ABBREV = {
  crusader: 'Cr',
  revenant: 'Re',
  blood_knight: 'BK',
  confessor: 'Co',
  shaman: 'Sh',
  mage: 'Ma',
  bard: 'Ba',
  plague_doctor: 'PD',
  ranger: 'Ra',
  inquisitor: 'In',
  hexblade: 'Hx',
};
```

### Performance Consideration

Computing `getPartyFitRoster()` for every bag item on every render would be expensive. Solution:

```javascript
// Memoize party fit results for all bag items
const bagFitResults = useMemo(() => {
  if (!partyMembers || partyMembers.length <= 1) return {};
  
  const results = {};
  for (const bagItem of viewInventory) {
    if (!bagItem?.equip_slot) continue;
    const key = bagItem.item_id || bagItem.name; // unique key per item
    results[key] = getPartyFitRoster(
      bagItem, partyMembers, partyInventories, players, effectiveUnitId
    );
  }
  return results;
}, [viewInventory, partyMembers, partyInventories, players, effectiveUnitId]);
```

This runs once per inventory change, not on every hover/render.

### Files Changed

| File | Changes |
|------|---------|
| **`client/src/utils/itemUtils.js`** | Add `CLASS_BADGE_ABBREV` constant; add `getBestFitBadge(partyFitRoster)` helper that returns `{ abbrev, color, count }` or `null` |
| **`client/src/components/Inventory/Inventory.jsx`** | Add `bagFitResults` memoized computation; render badge overlay on bag slots |
| **`client/src/styles/components/_inventory.css`** | Add `.bag-fit-badge` styles (positioned, circular, colored) |

### New Utility Function

**`client/src/utils/itemUtils.js`**:

```javascript
export const CLASS_BADGE_ABBREV = {
  crusader: 'Cr', revenant: 'Re', blood_knight: 'BK',
  confessor: 'Co', shaman: 'Sh', mage: 'Ma', bard: 'Ba',
  plague_doctor: 'PD', ranger: 'Ra', inquisitor: 'In', hexblade: 'Hx',
};

/**
 * From a partyFitRoster result, return badge info for the bag slot overlay.
 * Returns null if no upgrades exist.
 */
export function getBestFitBadge(roster) {
  if (!roster?.length) return null;
  
  const upgraders = roster.filter(r => r.fitScore > 0);
  if (upgraders.length === 0) return null;

  const best = roster.find(r => r.isBestFit);
  if (!best) return null;

  if (upgraders.length > 1) {
    return { label: `▲${upgraders.length}`, color: 'gold', tooltip: `Upgrade for ${upgraders.length} heroes` };
  }

  const abbrev = CLASS_BADGE_ABBREV[best.className] || best.className.charAt(0).toUpperCase();
  return { label: `▲${abbrev}`, color: best.isCurrentHero ? 'green-bright' : 'green', tooltip: `Upgrade for ${best.displayName}` };
}
```

### CSS Additions

```css
/* ── Best-Fit Badge on Bag Slots ── */
.bag-fit-badge {
  position: absolute;
  top: 1px;
  right: 1px;
  font-size: 0.4rem;
  font-family: var(--font-mono, monospace);
  font-weight: bold;
  padding: 0px 2px;
  border-radius: 2px;
  line-height: 1.1;
  pointer-events: none;
  z-index: 2;
  background: rgba(0, 0, 0, 0.7);
  border: 1px solid;
}

.bag-fit-badge.badge-green {
  color: #44cc44;
  border-color: rgba(68, 204, 68, 0.4);
}

.bag-fit-badge.badge-green-bright {
  color: #66ee66;
  border-color: rgba(102, 238, 102, 0.5);
  text-shadow: 0 0 3px rgba(102, 238, 102, 0.4);
}

.bag-fit-badge.badge-gold {
  color: #e8c252;
  border-color: rgba(232, 194, 82, 0.4);
}
```

### Verification

- [x] Bag items that are upgrades show a green badge with class abbreviation
- [x] Items that upgrade multiple heroes show gold badge with count
- [x] Items with no upgrades for anyone show no badge
- [x] Consumables and non-equippable items show no badge
- [x] Badges update when party composition changes (hero death, party tab switch)
- [x] Badges update when equipment changes (equip/unequip)
- [x] Performance is acceptable — memoized computation, not per-frame
- [x] Badges don't interfere with item rarity border or existing slot overlays
- [x] Solo mode (1 hero) shows no badges (nothing to compare against)

### Implementation Log — 21G-3

**Completed:** March 18, 2026

**Files Changed:**
| File | Changes |
|------|---------|
| `client/src/utils/itemUtils.js` | Added `CLASS_BADGE_ABBREV` constant (2-char abbreviations for all 11 classes) and `getBestFitBadge(roster)` — extracts best-fit badge info from a party fit roster, returning label/color/tooltip for single-upgrader (green + class abbrev) or multi-upgrader (gold + count) scenarios |
| `client/src/components/Inventory/Inventory.jsx` | Added `getPartyFitRoster` and `getBestFitBadge` imports; added `bagFitResults` useMemo that computes party fit rosters for all equippable bag items (keyed by instance_id/item_id/name), placed after `allPartyInventories`; added badge overlay `<span>` inside each bag slot's `bag-slot-content` div, rendered via IIFE that looks up the item's roster and badge |
| `client/src/styles/components/_inventory.css` | Added `.bag-fit-badge` (absolute positioned top-right, dark bg, mono font, pointer-events none, z-index 2) with `.badge-green` (upgrade for one hero), `.badge-green-bright` (upgrade for currently viewed hero, with glow), `.badge-gold` (upgrade for multiple heroes) |

**Key Implementation Details:**
- `bagFitResults` memo is guarded by `partyTabs.length <= 1` to skip computation entirely in solo mode — no badges rendered, no unnecessary calls
- Badge lookup uses `instance_id || item_id || name` as the key to match items in sorted and unsorted bag views
- The IIFE pattern in the bag slot render keeps badge computation local and avoids adding additional state
- `getBestFitBadge` returns `null` for items with no upgraders, so no badge element is rendered at all for non-upgrade items
- Badge uses `pointer-events: none` to avoid intercepting mouse events on the bag slot (hover/click still work as before)

---

## Implementation Notes

### Execution Order

1. **21G-1 first** — Party Fit Roster is the foundation. It introduces `getPartyFitRoster()` and the data flow (new props to tooltip).
2. **21G-2 second** — Q-to-Cycle builds on the same data flow and is independent of the badge system.
3. **21G-3 last** — Best-Fit Badges reuse `getPartyFitRoster()` from 21G-1 and benefit from the memoization pattern.

### Data Already Available

All required data is already in `useGameState()` — no server changes needed:

| Data | Source | Available |
|------|--------|-----------|
| `partyMembers[]` | `useGameState()` | ✅ Array of `{ unit_id, username, class_id, is_alive }` |
| `partyInventories{}` | `useGameState()` | ✅ `{ [unit_id]: { inventory: [], equipment: {} } }` |
| `players{}` | `useGameState()` | ✅ Full player state per unit |
| `compareItemsInline()` | `itemUtils.js` | ✅ Phase 21D |
| `getComparisonVerdict()` | `itemUtils.js` | ✅ Phase 21D |
| `getArmorAffinityInfo()` | `itemUtils.js` | ✅ Phase 21B |
| `CLASS_PREFERRED_ARMOR` | `itemUtils.js` | ✅ Phase 21B |

### No Server Changes Required

This is **100% client-side**. All game state needed for party comparison is already synced to the client via WebSocket. No new API endpoints, no model changes, no backend work.

### Performance Budget

- **21G-1 (Party Fit Roster):** 4 calls to `compareItemsInline()` per hover — each comparing ~20 stats. Negligible.
- **21G-2 (Q-to-Cycle):** Same as current tooltip — 1 call per viewed comparison. Zero overhead.
- **21G-3 (Best-Fit Badges):** `useMemo` recomputes only when `viewInventory`, `partyMembers`, `partyInventories`, `players`, or `effectiveUnitId` change. For a 20-slot bag with 4 heroes, that's ~80 `compareItemsInline()` calls per inventory change — still negligible (pure JS object comparison, no DOM work).

---

## Files Changed Summary

| File | 21G-1 | 21G-2 | 21G-3 | Total Changes |
|------|-------|-------|-------|---------------|
| **`client/src/utils/itemUtils.js`** | `getPartyFitRoster()` | — | `CLASS_BADGE_ABBREV`, `getBestFitBadge()` | 2 new functions, 1 constant |
| **`client/src/components/Inventory/ItemTooltip.jsx`** | Party Fit section | Compare target header | — | 2 new sections |
| **`client/src/components/Inventory/Inventory.jsx`** | Pass party props | Q-key handler + compare state | `bagFitResults` memo + badge render | 3 features |
| **`client/src/styles/components/_inventory.css`** | Party fit styles | Compare target styles | Badge styles | 3 style blocks |

---

## Summary: Before vs. After

| Aspect | Before (Phase 21D) | After (Phase 21G) |
|--------|--------------------|--------------------|
| Comparison scope | Current hero only | All party heroes visible |
| "Who needs this?" | Must switch tabs, re-hover, mentally compare | Instant Party Fit roster on every tooltip |
| Finding upgrades in bag | Hover each item, compare mentally | Colored badge on each bag slot shows best-fit hero |
| Comparing for another hero | Switch party tab → find item → hover again | Press Q to cycle through heroes in-place |
| "Should I vendor this?" | Difficult — might be useful for someone | Party Fit shows if any hero benefits |
| Solo mode impact | N/A | Features hidden with 1 hero — zero noise |

---

## Estimated Test Count

| Feature | New Tests (est.) |
|---------|-----------------|
| 21G-1 — `getPartyFitRoster()` unit tests | ~10 |
| 21G-1 — Tooltip rendering with party data | ~4 |
| 21G-2 — Q-key cycling state management | ~5 |
| 21G-3 — `getBestFitBadge()` unit tests | ~6 |
| 21G-3 — Badge rendering on bag slots | ~3 |
| **Total** | **~28 tests** |
