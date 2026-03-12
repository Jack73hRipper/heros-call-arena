"""
Pydantic models for items, equipment, inventory, and consumables.

Phase 4D-1: Pure data models — no gameplay logic.
"""

from __future__ import annotations

from enum import Enum
from pydantic import BaseModel, Field


# ---------- Enums ----------

class ItemType(str, Enum):
    WEAPON = "weapon"
    ARMOR = "armor"
    ACCESSORY = "accessory"
    CONSUMABLE = "consumable"


class Rarity(str, Enum):
    COMMON = "common"
    UNCOMMON = "uncommon"  # Legacy — Phase 15 tier, kept for backward compat
    MAGIC = "magic"        # Phase 16C — blue (replaces "uncommon" semantically)
    RARE = "rare"          # Phase 16C — yellow (3–4 random affixes)
    EPIC = "epic"          # Phase 16C — purple (4–5 random affixes)
    UNIQUE = "unique"      # Phase 16C — orange (hand-curated chase items)
    SET = "set"            # Phase 16C — green (set bonus items)


class EquipSlot(str, Enum):
    WEAPON = "weapon"
    ARMOR = "armor"
    ACCESSORY = "accessory"


class ConsumableType(str, Enum):
    HEAL = "heal"
    PORTAL = "portal"
    BUFF_ARMOR = "buff_armor"
    BUFF_DAMAGE = "buff_damage"


# ---------- Sub-models ----------

class StatBonuses(BaseModel):
    """Stat modifiers granted by an equipped item."""
    # Existing (Phase 4D)
    attack_damage: int = 0
    ranged_damage: int = 0
    armor: int = 0
    max_hp: int = 0

    # Phase 16A — Tier 1: Drop-in stats
    crit_chance: float = 0.0          # 0.0–0.50 (0–50%)
    crit_damage: float = 0.0          # 0.0–1.50 (additive with base 1.5×)
    dodge_chance: float = 0.0         # 0.0–0.40 (0–40%)
    damage_reduction_pct: float = 0.0 # 0.0–0.50 (0–50%)
    hp_regen: int = 0
    move_speed: int = 0

    # Phase 16A — Tier 2: New interactions
    life_on_hit: int = 0
    cooldown_reduction_pct: float = 0.0  # 0.0–0.30 (0–30%)
    skill_damage_pct: float = 0.0        # 0.0–0.40 (0–40%)
    thorns: int = 0
    gold_find_pct: float = 0.0           # 0.0–0.80 (0–80%)
    magic_find_pct: float = 0.0          # 0.0–0.60 (0–60%)

    # Phase 16A — Tier 3: Class/build-defining
    holy_damage_pct: float = 0.0      # 0.0–0.40 (0–40%)
    dot_damage_pct: float = 0.0       # 0.0–0.40 (0–40%)
    heal_power_pct: float = 0.0       # 0.0–0.40 (0–40%)
    armor_pen: int = 0


class ConsumableEffect(BaseModel):
    """Effect applied when a consumable is used."""
    type: ConsumableType
    magnitude: int = 0  # e.g. HP restored for heal; 0 for portal (special handling)
    duration: int = 0   # Turns the effect lasts (0 = instant, >0 = buff)


# ---------- Core Item Model ----------

class Item(BaseModel):
    """A single item instance.

    Phase 16B: Items are now uniquely identified by instance_id (UUID).
    item_id is kept for backward compat and equals base_type_id for non-affix items.
    Generated items have random affixes rolled on top of their base stats.
    """
    item_id: str
    name: str
    item_type: ItemType
    rarity: Rarity = Rarity.COMMON
    equip_slot: EquipSlot | None = None  # None for consumables
    stat_bonuses: StatBonuses = Field(default_factory=StatBonuses)
    consumable_effect: ConsumableEffect | None = None  # Only for consumables
    description: str = ""
    sell_value: int = 0  # Gold value when sold to merchant (used in 4F)

    # Phase 16B: Affix system fields
    instance_id: str = ""              # UUID — unique per drop; empty for legacy/static items
    base_type_id: str = ""             # References items_config base type; empty for legacy items
    display_name: str = ""             # Base name without affixes (e.g., "Greatsword")
    base_stats: StatBonuses = Field(default_factory=StatBonuses)  # Base type stats only
    affixes: list[dict] = Field(default_factory=list)  # [{affix_id, type, name, stat, value}, ...]
    item_level: int = 1                # Determines affix roll ranges
    # Phase 16 — Weapon class-lock system
    weapon_category: str = ""          # "melee", "ranged", "caster", "hybrid", or "" for non-weapons


# ---------- Inventory ----------

INVENTORY_MAX_CAPACITY = 10


class Inventory(BaseModel):
    """A hero's personal inventory (bag). Max 10 slots."""
    items: list[Item] = Field(default_factory=list)
    max_capacity: int = INVENTORY_MAX_CAPACITY

    def is_full(self) -> bool:
        """Check if the inventory is at max capacity."""
        return len(self.items) >= self.max_capacity

    def free_slots(self) -> int:
        """Number of remaining free slots."""
        return max(0, self.max_capacity - len(self.items))

    def add_item(self, item: Item) -> bool:
        """Add an item to inventory. Returns False if full."""
        if self.is_full():
            return False
        self.items.append(item)
        return True

    def remove_item(self, item_id: str) -> Item | None:
        """Remove and return the first item matching item_id. Returns None if not found.

        Phase 16B: Also checks instance_id for generated items.
        """
        # First try instance_id match (for generated items with UUID)
        for i, item in enumerate(self.items):
            if item.instance_id and item.instance_id == item_id:
                return self.items.pop(i)
        # Fallback to item_id match (for legacy/static items)
        for i, item in enumerate(self.items):
            if item.item_id == item_id:
                return self.items.pop(i)
        return None

    def has_item(self, item_id: str) -> bool:
        """Check if inventory contains at least one item with the given ID."""
        return any(item.item_id == item_id for item in self.items)

    def count_item(self, item_id: str) -> int:
        """Count how many of a specific item are in inventory."""
        return sum(1 for item in self.items if item.item_id == item_id)

    def get_consumables(self) -> list[Item]:
        """Get all consumable items in inventory."""
        return [item for item in self.items if item.item_type == ItemType.CONSUMABLE]


# ---------- Equipment ----------

class Equipment(BaseModel):
    """A hero's equipped gear. Three slots: weapon, armor, accessory."""
    weapon: Item | None = None
    armor: Item | None = None
    accessory: Item | None = None

    def get_slot(self, slot: EquipSlot) -> Item | None:
        """Get the item in a specific equipment slot."""
        return getattr(self, slot.value, None)

    def set_slot(self, slot: EquipSlot, item: Item | None) -> None:
        """Set an item in a specific equipment slot."""
        setattr(self, slot.value, item)

    def equip(self, item: Item) -> Item | None:
        """Equip an item in its designated slot. Returns the previously equipped
        item (if any) so the caller can put it back in inventory."""
        if item.equip_slot is None:
            return None  # Consumables can't be equipped
        slot = item.equip_slot
        previous = self.get_slot(slot)
        self.set_slot(slot, item)
        return previous

    def unequip(self, slot: EquipSlot) -> Item | None:
        """Remove and return the item in a slot. Returns None if slot is empty."""
        item = self.get_slot(slot)
        if item is not None:
            self.set_slot(slot, None)
        return item

    def total_bonuses(self) -> StatBonuses:
        """Sum stat bonuses from all equipped items."""
        total = StatBonuses()
        for slot in EquipSlot:
            item = self.get_slot(slot)
            if item is not None:
                bonuses = item.stat_bonuses
                total.attack_damage += bonuses.attack_damage
                total.ranged_damage += bonuses.ranged_damage
                total.armor += bonuses.armor
                total.max_hp += bonuses.max_hp
                # Phase 16A: Aggregate new stats
                total.crit_chance += bonuses.crit_chance
                total.crit_damage += bonuses.crit_damage
                total.dodge_chance += bonuses.dodge_chance
                total.damage_reduction_pct += bonuses.damage_reduction_pct
                total.hp_regen += bonuses.hp_regen
                total.move_speed += bonuses.move_speed
                total.life_on_hit += bonuses.life_on_hit
                total.cooldown_reduction_pct += bonuses.cooldown_reduction_pct
                total.skill_damage_pct += bonuses.skill_damage_pct
                total.thorns += bonuses.thorns
                total.gold_find_pct += bonuses.gold_find_pct
                total.magic_find_pct += bonuses.magic_find_pct
                total.holy_damage_pct += bonuses.holy_damage_pct
                total.dot_damage_pct += bonuses.dot_damage_pct
                total.heal_power_pct += bonuses.heal_power_pct
                total.armor_pen += bonuses.armor_pen
        return total

    def equipped_items(self) -> list[Item]:
        """Return a list of all currently equipped items (non-None)."""
        return [
            item for slot in EquipSlot
            if (item := self.get_slot(slot)) is not None
        ]
