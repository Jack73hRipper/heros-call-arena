"""
Pydantic models for player state, class definitions, and enemy definitions.
"""

from __future__ import annotations

import json
import random
from pathlib import Path

from pydantic import BaseModel, Field


class Position(BaseModel):
    x: int = 0
    y: int = 0


class PlayerState(BaseModel):
    """In-match state of a single player (or AI unit)."""
    player_id: str
    username: str
    position: Position = Field(default_factory=Position)
    hp: int = 100
    max_hp: int = 100
    attack_damage: int = 15
    ranged_damage: int = 10
    armor: int = 2
    is_alive: bool = True
    is_ready: bool = False
    vision_range: int = 7
    ranged_range: int = 5
    # Cooldowns: key = ability name, value = turns remaining
    cooldowns: dict[str, int] = Field(default_factory=dict)
    # Team and type for Phase 2
    unit_type: str = "human"  # "human" or "ai"
    team: str = "a"  # "a" or "b"
    # Phase 4A: Class system
    class_id: str | None = None  # e.g. "crusader", "ranger", etc. None = legacy/default
    # Phase 4C: Enemy type system
    enemy_type: str | None = None  # e.g. "demon", "skeleton", "undead_knight". None = player/arena AI
    ai_behavior: str | None = None  # e.g. "aggressive", "ranged", "boss". None = default AI
    room_id: str | None = None  # Room this enemy is assigned to (for leashing). None = no leash
    is_boss: bool = False  # True for boss enemies (visual + gameplay distinction)
    # Phase 27: PVPVE team leader — first unit per AI team is the anchor others follow
    is_team_leader: bool = False
    # Phase 4D: Equipment & Inventory (individual hero inventory)
    # Equipment: dict keyed by slot name ("weapon", "armor", "accessory") -> serialized Item dict
    # Stored as raw dicts for JSON/Redis serialization. Convert to Item models when needed.
    equipment: dict = Field(default_factory=dict)   # {"weapon": {...}, "armor": {...}, "accessory": {...}}
    # Inventory: list of serialized Item dicts, max 10 slots (INVENTORY_MAX_CAPACITY)
    inventory: list = Field(default_factory=list)    # [{item_id, name, ...}, ...]
    # Phase 4E-2: Persistent hero tracking
    hero_id: str | None = None  # Links to a persistent Hero on a PlayerProfile. None = arena/legacy mode
    sprite_variant: int = 1  # Sprite visual variant (1-3) — persisted on the Hero, forwarded to client
    # Phase 5: Party control — when set, this AI unit accepts commands from the controlling player
    controlled_by: str | None = None  # owner player_id who is currently issuing commands. None = full AI autonomy
    # Phase 6A: Active buffs/debuffs — list of {buff_id, stat, magnitude, turns_remaining}
    active_buffs: list[dict] = Field(default_factory=list)
    # Phase 11: Creature type tags for bonus-damage skills ("undead", "demon", etc.)
    tags: list[str] = Field(default_factory=list)
    # Training room: Invulnerable units cannot die (HP resets after each hit)
    invulnerable: bool = False
    # Phase 7C: AI behavior stance — controls how hero allies behave between/during combat
    # "follow" (default), "aggressive", "defensive", "hold"
    ai_stance: str = "follow"
    # Phase 10A: Auto-target — persistent melee pursuit target
    # When set, the server generates chase/attack actions each tick if the player's queue is empty.
    # Cleared when: target dies, player issues a new command, player cancels, target unreachable.
    auto_target_id: str | None = None
    # Phase 10G: Skill auto-target — when set alongside auto_target_id, the server generates
    # SKILL actions instead of ATTACK when in range. None = melee pursuit (Phase 10 default).
    auto_skill_id: str | None = None
    # Phase 12C: Portal extraction — True when this hero has entered the portal and escaped
    extracted: bool = False

    # Phase 16A: Expanded combat stats (computed from base + equipment + buffs)
    crit_chance: float = 0.05       # Default 5% base crit chance
    crit_damage: float = 1.5        # Default 150% crit multiplier
    dodge_chance: float = 0.0
    damage_reduction_pct: float = 0.0
    hp_regen: int = 0
    move_speed: int = 0
    life_on_hit: int = 0
    cooldown_reduction_pct: float = 0.0
    skill_damage_pct: float = 0.0
    thorns: int = 0
    gold_find_pct: float = 0.0
    magic_find_pct: float = 0.0
    holy_damage_pct: float = 0.0
    dot_damage_pct: float = 0.0
    magic_damage_pct: float = 0.0      # Phase 17: Mage spell damage bonus
    heal_power_pct: float = 0.0
    armor_pen: int = 0

    # Phase 16E: Active set bonuses — recalculated whenever equipment changes
    active_set_bonuses: list[dict] = Field(default_factory=list)

    # Phase 18A: Monster rarity system
    monster_rarity: str | None = None          # "normal", "champion", "rare", "super_unique"
    champion_type: str | None = None           # "berserker", "fanatic", "ghostly", "resilient", "possessed"
    affixes: list[str] = Field(default_factory=list)  # ["extra_strong", "fire_enchanted", ...]
    display_name: str | None = None            # Generated name: "Blazing Skeleton the Pyreborn"
    minion_owner_id: str | None = None         # For rare minions: ID of the rare that spawned them
    is_minion: bool = False                    # True if spawned as a rare's minion pack


class ClassDefinition(BaseModel):
    """Definition of a playable class loaded from classes_config.json."""
    class_id: str
    name: str
    role: str
    description: str = ""
    base_hp: int = 100
    base_melee_damage: int = 15
    base_ranged_damage: int = 10
    base_armor: int = 2
    base_vision_range: int = 7
    ranged_range: int = 5
    # Phase 16: Weapon class-lock — which weapon categories this class can equip
    allowed_weapon_categories: list[str] = Field(default_factory=list)
    color: str = "#ffffff"
    shape: str = "circle"  # circle, square, triangle, diamond, star


class EnemyDefinition(BaseModel):
    """Definition of an enemy type loaded from enemies_config.json."""
    enemy_id: str
    name: str
    role: str
    description: str = ""
    base_hp: int = 100
    base_melee_damage: int = 15
    base_ranged_damage: int = 0
    base_armor: int = 2
    base_vision_range: int = 5
    ranged_range: int = 1
    ai_behavior: str = "aggressive"
    color: str = "#cc3333"
    shape: str = "diamond"
    is_boss: bool = False
    # Enemy class_id for skill usage — maps to class_skills and AI role handlers
    class_id: str | None = None
    # Phase 11: Creature type tags for bonus damage skills (e.g. "undead", "demon")
    tags: list[str] = Field(default_factory=list)
    # Training room: Invulnerable enemies cannot die
    invulnerable: bool = False
    # Phase 18A: Affix exclusions (affixes that don't make sense on this enemy)
    excluded_affixes: list[str] = Field(default_factory=list)
    # Phase 18A: Whether this enemy can be upgraded to champion/rare
    allow_rarity_upgrade: bool = True  # False for training_dummy, bosses handled separately


# ---------- Class Config Loader ----------

_classes_config_path = Path(__file__).resolve().parent.parent.parent / "configs" / "classes_config.json"
_classes_cache: dict[str, ClassDefinition] | None = None


def load_classes_config(path: Path | None = None) -> dict[str, ClassDefinition]:
    """Load class definitions from JSON config. Caches after first load."""
    global _classes_cache
    if _classes_cache is not None:
        return _classes_cache

    config_file = path or _classes_config_path
    if config_file.exists():
        with open(config_file, "r") as f:
            raw = json.load(f)
        _classes_cache = {}
        for cid, cdata in raw.get("classes", {}).items():
            _classes_cache[cid] = ClassDefinition(**cdata)
    else:
        _classes_cache = {}
    return _classes_cache


def get_class_definition(class_id: str) -> ClassDefinition | None:
    """Get a single class definition by ID. Returns None if not found."""
    classes = load_classes_config()
    return classes.get(class_id)


def get_all_classes() -> dict[str, ClassDefinition]:
    """Get all class definitions."""
    return load_classes_config()


def apply_class_stats(player: PlayerState, class_id: str) -> bool:
    """Apply class stats to a PlayerState. Returns True on success."""
    class_def = get_class_definition(class_id)
    if not class_def:
        return False
    player.class_id = class_id
    player.hp = class_def.base_hp
    player.max_hp = class_def.base_hp
    player.attack_damage = class_def.base_melee_damage
    player.ranged_damage = class_def.base_ranged_damage
    player.armor = class_def.base_armor
    player.vision_range = class_def.base_vision_range
    player.ranged_range = class_def.ranged_range
    return True


# ---------- Enemy Config Loader (Phase 4C) ----------

_enemies_config_path = Path(__file__).resolve().parent.parent.parent / "configs" / "enemies_config.json"
_enemies_cache: dict[str, EnemyDefinition] | None = None


def load_enemies_config(path: Path | None = None) -> dict[str, EnemyDefinition]:
    """Load enemy definitions from JSON config. Caches after first load."""
    global _enemies_cache
    if _enemies_cache is not None:
        return _enemies_cache

    config_file = path or _enemies_config_path
    if config_file.exists():
        with open(config_file, "r") as f:
            raw = json.load(f)
        _enemies_cache = {}
        for eid, edata in raw.get("enemies", {}).items():
            _enemies_cache[eid] = EnemyDefinition(**edata)
    else:
        _enemies_cache = {}
    return _enemies_cache


def get_enemy_definition(enemy_id: str) -> EnemyDefinition | None:
    """Get a single enemy definition by ID. Returns None if not found."""
    enemies = load_enemies_config()
    return enemies.get(enemy_id)


def get_all_enemies() -> dict[str, EnemyDefinition]:
    """Get all enemy definitions."""
    return load_enemies_config()


def apply_enemy_stats(player: PlayerState, enemy_id: str, room_id: str | None = None) -> bool:
    """Apply enemy type stats to a PlayerState. Returns True on success.

    Sets HP, damage, armor, vision, behavior, and enemy_type fields.
    The unit is also marked as AI and assigned to enemy team 'b'.
    Assigns a random sprite variant from available enemy sprites.
    """
    # Number of sprite variants available per enemy type
    ENEMY_SPRITE_VARIANTS = {
        "demon": 2,
        "skeleton": 1,
        "undead_knight": 3,
        "imp": 4,
        "wraith": 3,
        "medusa": 2,
        "acolyte": 3,
        "werewolf": 2,
        "reaper": 1,
        "construct": 3,
        "imp_lord": 1,
        "demon_boss": 1,
        "demon_knight": 1,
        "construct_boss": 1,
        "ghoul": 1,
        "necromancer": 1,
        "undead_caster": 1,
        "horror": 2,
        "insectoid": 2,
        "caster": 2,
        "evil_snail": 1,
        "goblin_spearman": 1,
        "shade": 1,
    }
    enemy_def = get_enemy_definition(enemy_id)
    if not enemy_def:
        return False
    player.enemy_type = enemy_id
    player.ai_behavior = enemy_def.ai_behavior
    player.is_boss = enemy_def.is_boss
    player.room_id = room_id
    player.tags = list(enemy_def.tags)  # Phase 11: copy creature tags
    # Assign random sprite variant for visual variety
    max_variants = ENEMY_SPRITE_VARIANTS.get(enemy_id, 1)
    player.sprite_variant = random.randint(1, max_variants)
    # Enemy class_id enables skill usage via AI skill framework
    if enemy_def.class_id:
        player.class_id = enemy_def.class_id
    player.hp = enemy_def.base_hp
    player.max_hp = enemy_def.base_hp
    player.attack_damage = enemy_def.base_melee_damage
    player.ranged_damage = enemy_def.base_ranged_damage
    player.armor = enemy_def.base_armor
    player.vision_range = enemy_def.base_vision_range
    player.ranged_range = enemy_def.ranged_range
    player.invulnerable = enemy_def.invulnerable
    return True


class PlayerJoinRequest(BaseModel):
    username: str


class PlayerReadyRequest(BaseModel):
    player_id: str
    ready: bool = True
