# Weapon Class-Lock System

**Created:** March 3, 2026  
**Status:** Implemented  
**Phase:** 16 (Item & Equipment Overhaul)  
**Scope:** Prevents classes from equipping weapon categories that don't match their identity.

---

## Overview

Weapons are now assigned a `weapon_category` that determines which classes can equip them. This prevents "stat trap" scenarios (e.g., a Ranger equipping a melee sword and gaining zero benefit) and reinforces class identity established in Phases 8–11.

**Auto-attacks remain class-determined, not weapon-determined.** A Crusader always melees adjacent targets; a Ranger always fires at range. Weapons are stat sticks — they boost the numbers your class already uses.

---

## Weapon Categories

| Category | Description | Stat Focus | Example Items |
|----------|-------------|------------|---------------|
| `melee` | Close-combat weapons | `attack_damage`, crit, holy | Sword, Mace, Dagger, Flail, Warhammer, Stiletto, Greatsword |
| `ranged` | Projectile weapons | `ranged_damage`, armor pen, DoT | Bow, Crossbow, Longbow |
| `caster` | Spell-amplifying weapons | `skill_damage_pct`, CDR, heal power | Staff |
| `hybrid` | Dual-purpose weapons | Both `attack_damage` + `ranged_damage` | Throwing Axes, War Axes |

---

## Class Weapon Permissions

| Class | Allowed Categories | Rationale |
|-------|--------------------|-----------|
| **Crusader** | `melee`, `hybrid` | Frontline tank — swords, maces, flails, throwing axes. No bows or staves. |
| **Confessor** | `melee`, `caster`, `hybrid` | Support/healer — maces, flails, staves (spell focus). No bows. |
| **Inquisitor** | `ranged`, `caster`, `hybrid` | Scout/demon hunter — bows, crossbows, staves, throwing axes. No pure melee. |
| **Ranger** | `ranged`, `hybrid` | Pure ranged DPS — bows, crossbows, throwing axes. No melee or staves. |
| **Hexblade** | `melee`, `ranged`, `caster`, `hybrid` | True hybrid — can equip anything. Reflects hybrid DPS identity. |

### Visual Matrix

```
                  melee   ranged   caster   hybrid
Crusader           ✓                          ✓
Confessor          ✓                ✓         ✓
Inquisitor                  ✓       ✓         ✓
Ranger                      ✓                 ✓
Hexblade           ✓        ✓       ✓         ✓
```

---

## Unique & Set Item Categorization

### Unique Weapons

| Item | Category | Best For |
|------|----------|----------|
| Soulreaver | `melee` | Crusader, Hexblade |
| The Whisper | `ranged` | Ranger, Inquisitor |
| Grimfang | `melee` | Hexblade |
| Dawnbreaker | `melee` | Confessor, Inquisitor (note: Inquisitor can't equip — holy melee weapon for Crusader/Confessor/Hexblade) |
| Plaguebow | `ranged` | Ranger |
| Voidedge | `hybrid` | Hexblade, Inquisitor |

### Set Weapons

| Set | Weapon | Category | Class Affinity |
|-----|--------|----------|----------------|
| Crusader's Oath | Warhammer | `melee` | Crusader |
| Voidwalker's Regalia | Blade | `hybrid` | Hexblade |
| Deadeye's Arsenal | Longbow | `ranged` | Ranger |
| Faith's Radiance | Staff | `caster` | Confessor |
| Seeker's Judgment | Crossbow | `ranged` | Inquisitor |

---

## Implementation Details

### Files Changed

| File | Change |
|------|--------|
| `server/configs/items_config.json` | Added `weapon_category` to all 16 weapon entries |
| `server/configs/classes_config.json` | Added `allowed_weapon_categories` array to all 5 classes |
| `server/configs/uniques_config.json` | Added `weapon_category` to all 6 unique weapons |
| `server/configs/sets_config.json` | Added `weapon_category` to all 5 set weapon pieces |
| `server/app/models/items.py` | Added `weapon_category: str = ""` field to `Item` model |
| `server/app/models/player.py` | Added `allowed_weapon_categories: list[str]` to `ClassDefinition` |
| `server/app/core/equipment_manager.py` | Added class-lock validation in `equip_item()` |
| `server/app/routes/town.py` | Added class-lock validation in town `equip_item()` endpoint |
| `server/app/core/item_generator.py` | Propagated `weapon_category` through `generate_item()`, `generate_unique_item()`, `generate_set_piece()` |

### Enforcement Points

Weapon class-lock is enforced at **two** equip entry points:

1. **In-match equip** — `equipment_manager.equip_item()` (WebSocket `equip_item` message)
2. **Town equip** — `town.equip_item()` (REST POST `/town/equip`)

Both check: if the item is a weapon with a `weapon_category`, look up the player/hero's `class_id`, get the class definition's `allowed_weapon_categories`, and reject if the category isn't in the allowed list.

### Backward Compatibility

- Items without `weapon_category` (empty string) bypass the check — legacy items still work
- Classes without `allowed_weapon_categories` (empty list) bypass the check — no restriction
- Enemy/AI units without `class_id` bypass the check
- Armor and accessories are NOT class-locked (any class can equip any armor/accessory)

---

## Design Decisions

### Why NOT weapon-dictates-auto-attack?

Letting weapons change a unit's attack type (melee ↔ ranged) was rejected because:

1. **AI system assumes class = attack type.** Stance-based behavior (Phase 8), kiting logic (Phase 8K), auto-target pursuit (Phase 10) all key off `ranged_range` which is a class property.
2. **Skill kits are built around class identity.** A melee-wielding Ranger would have Power Shot but no ranged attack — nonsensical.
3. **Balance complexity.** Would require rebalancing every class's stat curve, AI priorities, and skill interactions.

### Why NOT soft penalty instead of hard lock?

A "reduced effectiveness" approach (e.g., Ranger gets 50% of melee weapon stats) was rejected because:
- Hard to communicate to players — tooltip would need complex conditional text
- Still results in suboptimal equips that feel bad
- Diablo's model (hard class restrictions) is proven and well-understood

### Why Hexblade gets everything

Hexblade's identity is "true hybrid" — equal melee and ranged damage, curse specialist. Allowing all weapon categories reinforces that unique flexibility and makes the class feel distinct.

### Staves as "caster" weapons

Staves technically give small `attack_damage` (for the rare melee swing) but their real value is `skill_damage_pct`, `cooldown_reduction_pct`, and `heal_power_pct`. Confessor and Inquisitor can equip them as "stat sticks" for their spell kits. Ranger cannot — Rangers don't use spells so staves would be a stat trap.

---

## Future Considerations

### Adding New Weapon Categories

To add a new category (e.g., `holy` for blessed weapons):
1. Add the category string to weapon entries in the relevant config
2. Add it to `allowed_weapon_categories` for appropriate classes in `classes_config.json`
3. No code changes needed — the system is fully data-driven

### Adding New Classes

New classes just need `allowed_weapon_categories` in their class definition. If omitted, the class can equip any weapon (no restriction — backward-compatible default).

### Client-Side Improvements (Future)

Consider adding:
- Grey out / dim weapons the current hero can't equip in inventory UI
- Tooltip text: "Cannot equip: [Class] cannot use [category] weapons"
- Item Forge tool: weapon_category dropdown in item creation
- Loot filter: option to auto-hide incompatible weapon drops

### Armor Class-Locking (Not Planned)

Currently any class can equip any armor. If we want heavy/medium/light armor restrictions later:
- Add `armor_category` field to armor items (e.g., "heavy", "medium", "light", "cloth")
- Add `allowed_armor_categories` to class definitions
- Use the same enforcement pattern as weapons

This is not currently planned — armor diversity (tank wearing light armor for dodge, caster wearing plate for survival) creates interesting trade-offs.
