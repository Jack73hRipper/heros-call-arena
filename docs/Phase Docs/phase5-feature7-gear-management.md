# Phase 5 Feature 7: Town Gear Management

## Overview

Heroes can now manage their equipment and inventory directly from the Town Hub's Hero Roster tab. Clicking a hero card opens a full gear management panel where players can equip/unequip items, view stat bonuses from gear, and transfer items between heroes.

## What Was Built

### Server (3 new REST endpoints + helpers)

| Endpoint | Method | Body | Description |
|---|---|---|---|
| `/api/town/equip` | POST | `{username, hero_id, item_index}` | Move item from hero's bag → equipment slot. Swaps if slot occupied. |
| `/api/town/unequip` | POST | `{username, hero_id, slot}` | Move item from equipment slot → bag. Fails if bag full. |
| `/api/town/transfer` | POST | `{username, from_hero_id, to_hero_id, item_index}` | Move item from one hero's bag to another's. |

**Helper functions** added to `server/app/routes/town.py`:
- `_hydrate_equipment(raw_dict)` — Converts raw equipment dict → typed `Equipment` model
- `_hydrate_inventory(raw_list)` — Converts raw inventory list → typed `Inventory` model
- `_serialize_equipment(Equipment)` — Converts back to raw dict for persistence
- `_serialize_inventory(Inventory)` — Converts back to raw list for persistence

These helpers bridge the gap between the raw `dict`/`list` storage format on `Hero` and the typed Pydantic `Equipment`/`Inventory` models that have the `.equip()` / `.unequip()` logic.

### Client (1 new component + 3 reducer actions + CSS)

**New Component:** `client/src/components/TownHub/HeroDetailPanel.jsx`
- Full overlay panel opened by clicking a hero card in the Roster
- Left column: Stats (with equipment bonus breakdown), 3 equipment slots, "Select for Dungeon" button
- Right column: 10-slot bag grid with Equip/Transfer buttons per item
- Item tooltips on hover with rarity colors, stat bonuses, descriptions
- Transfer modal with hero picker showing bag capacity
- Action feedback messages (success/error)

**Modified Components:**
- `HeroRoster.jsx` — Added click-to-manage behavior on hero cards + "Manage Gear" button + HeroDetailPanel integration
- `GameStateContext.jsx` — 3 new reducer actions:
  - `HERO_EQUIP` — Updates hero equipment + inventory from server response
  - `HERO_UNEQUIP` — Same shape as HERO_EQUIP
  - `HERO_TRANSFER` — Updates both source and destination hero inventories

**CSS** — ~400 lines of grimdark-themed styles in `main.css`:
- Overlay backdrop with fade-in animation
- Panel with slide-up animation and ember glow shadow
- Equipment slot rows with unequip-on-click and hover state
- Bag grid with Equip/Transfer action buttons
- Transfer modal with hero picker cards
- Rarity border colors (common/uncommon)
- Responsive layout (stacks on narrow screens)

### Tests (33 new tests)

File: `server/tests/test_gear_management.py`

| Category | Count | Tests |
|---|---|---|
| Hydrate/Serialize | 5 | Empty equipment, populated equipment, empty inventory, populated inventory, roundtrip |
| Equip | 10 | Weapon/armor/accessory to empty slot, swap occupied slot, consumable rejected, invalid/negative index, dead hero, hero not found, persistence |
| Unequip | 7 | Weapon, armor, empty slot rejected, invalid slot rejected, full inventory rejected, dead hero, persistence |
| Transfer | 8 | Basic transfer, data preservation, same hero rejected, full destination rejected, invalid index, dead source, dead destination, persistence |
| Integration | 3 | Equip→unequip roundtrip, equip all three slots, full equip→unequip→transfer flow |

## How It Works

### User Flow

```
Town Hub → Hero Roster tab
  └── Click any hero card (or "⚙️ Manage Gear" button)
        └── Hero Detail Panel opens as overlay
              ├── View stats with equipment bonus breakdown (+X shown in green)
              ├── Equipment slots: click to unequip → item returns to bag
              ├── Bag items: click "Equip" → moves to equipment slot
              │     └── If slot occupied: old item swaps back to bag
              ├── Bag items: click "Transfer" → opens hero picker modal
              │     └── Select destination hero → item moves to their bag
              ├── "Select for Dungeon" button still accessible
              └── Click ✕ or click outside panel to close
```

### Data Flow

```
Client click → fetch('/api/town/equip', {...})
  → Server: load profile → hydrate models → Equipment.equip() → serialize → save
  → Response: { status, hero_id, equipment, inventory }
  → Client: dispatch('HERO_EQUIP', payload) → reducer updates hero in state
  → React re-render: panel reflects new equipment/inventory
```

### Equip Swap Logic

When equipping an item to an already-occupied slot:
1. Item is removed from inventory at `item_index`
2. `Equipment.equip(item)` returns the previously equipped item
3. Previous item is inserted back into inventory at the same index
4. Net result: items swap positions (bag ↔ equipment slot)

## Validation Rules

| Operation | Validations |
|---|---|
| Equip | Hero exists + is alive, valid item index, item has `equip_slot` (not consumable) |
| Unequip | Hero exists + is alive, valid slot name, slot is not empty, inventory not full (10/10) |
| Transfer | Both heroes exist + alive, different heroes, valid item index, destination bag not full |

## Files Changed

| File | Change |
|---|---|
| `server/app/routes/town.py` | +3 endpoints, +4 helper functions, updated imports/docstring |
| `client/src/components/TownHub/HeroDetailPanel.jsx` | **New file** — gear management panel |
| `client/src/components/TownHub/HeroRoster.jsx` | Added click-to-manage, "Manage Gear" button, panel integration |
| `client/src/context/GameStateContext.jsx` | +3 reducer actions (HERO_EQUIP, HERO_UNEQUIP, HERO_TRANSFER) |
| `client/src/styles/main.css` | +~400 lines of gear management CSS |
| `server/tests/test_gear_management.py` | **New file** — 33 tests |
| `README.md` | Updated phase status, test counts |

## Backward Compatibility

- **627 tests passing** (594 existing + 33 new, 0 failures)
- All existing endpoints unchanged
- No modifications to in-match inventory/equipment systems
- Arena mode completely unaffected
- Client builds cleanly (0 errors)

---

## Future QoL Improvements

### 1. Shared Bank / Stash System ✅ COMPLETE
- `PlayerProfile.bank` field — account-wide storage (20 slots)
- Items in bank persist across hero deaths (permadeath protection)
- Strategic value: bank valuable gear before risky dungeon runs
- Endpoints: `GET /api/town/bank`, `POST /api/town/bank/deposit`, `POST /api/town/bank/withdraw`
- New Town Hub tab: "🏦 Bank" — two-column layout (vault + hero inventory)
- 26 tests covering deposit, withdraw, validation, persistence, and integration
- `BANK_MAX_CAPACITY = 20` constant in `profile.py`
- `BANK_DEPOSIT` / `BANK_WITHDRAW` reducer actions in `GameStateContext.jsx`

### 2. Quick-Equip from Merchant
- After buying an item, option to equip it immediately instead of buying → bag → equip
- "Buy & Equip" button on merchant items when hero has the slot free

### 3. Equipment Comparison Tooltip
- When hovering over a bag item, show a side-by-side comparison with the currently equipped item in that slot
- Green/red stat deltas: "+3 Armor" vs current equipped

### 4. "Equip Best" Auto-Equip Button
- One-click button that auto-equips the highest stat-value item per slot from the hero's bag
- Useful after returning from a dungeon with lots of loot

### 5. Item Sorting
- Sort bag items by: type (weapons first), rarity, name, sell value
- Persistent sort preference per player

### 6. Drag-and-Drop Gear Management
- Drag items between bag slots, equipment slots, and between hero panels
- More intuitive than click-based actions

### 7. Gear Sets / Loadouts
- Save named equipment configurations (e.g., "Melee Build", "Tank Build")
- One-click swap between registered gear sets

### 8. Bulk Transfer
- Select multiple items in bag → transfer all at once to another hero
- Useful when preparing a hero for a specific dungeon run

### 9. Item Locking
- Lock items to prevent accidental selling or transferring
- Visual padlock icon on locked items

### 10. Effective Stats Display
- Show the hero's total effective stats (base + all equipment bonuses combined) as a single number
- Separate "base" vs "total" display in the stats panel
- Show stat comparison when selecting a hero for dungeon (effective power rating)
